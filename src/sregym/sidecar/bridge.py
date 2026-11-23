"""Harbor bridge for one SREGym problem.

Runs inside the privileged ``sregym`` sidecar, after SREGym's DinD entrypoint
has started a private Docker daemon and a four-node KIND cluster. It runs the
unmodified SREGym campaign (``main.py``) in-process for a single problem:

    deploy app -> baseline -> inject fault -> conductor stages
    (diagnosis -> mitigation) -> oracle evaluation -> cleanup

The campaign runs in SREGym's default *filtered* mode, with SREGym's passive
``debug`` agent registered in place of a real one. The real agent is Harbor's
agent in the ``main`` container. Like SREGym's own drivers, it talks to the
conductor API (port 8000) and to the filtering Kubernetes API proxy
(port 16443). SREGym's nested agent containers reach the proxy at
``host.docker.internal``. The compose file gives this sidecar the same alias,
so the agent kubeconfig SREGym generates works unchanged in ``main``.

On port 8100 the bridge adds a small HTTP API, used only by Harbor's verifier
and oracle:

    GET  /harbor/health             readiness (also written to /run/harbor-ready)
    POST /harbor/finish             the Harbor agent has finished; stop the
                                    passive agent so the conductor finalizes
    GET  /harbor/result             conductor results once the attempt is final
    GET  /harbor/oracle/root_cause  ground-truth root cause   (token required)
    POST /harbor/oracle/recover     problem.recover_fault()   (token required)

The oracle endpoints require a per-task token: an HMAC of a private secret
chosen when the tasks are generated (random by default, never committed). It
is present only in this container's environment and in the task's
``solution/`` directory, which Harbor uploads for the oracle agent alone.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SREGYM_ROOT = Path(os.environ.get("SREGYM_ROOT", "/opt/sregym"))
SHARED_DIR = Path(os.environ.get("HARBOR_SHARED_DIR", "/harbor-shared"))
READY_FILE = Path("/run/harbor-ready")
# Collected by the task as an artifact from this service (task.toml), also when
# the environment fails to start. The DinD entrypoint already writes dockerd.log
# (and KIND logs on cluster failure) under results/dind/.
LOG_FILE = SREGYM_ROOT / "results" / "harbor" / "sidecar.log"
BRIDGE_PORT = int(os.environ.get("HARBOR_BRIDGE_PORT", "8100"))
PROXY_PORT = int(os.environ.get("K8S_PROXY_PORT", "16443"))
# Upstream's own passive agent name: filtered mode knows it needs no model
# endpoints (sregym/service/provider_endpoints.py).
AGENT_NAME = "debug"

logging.basicConfig(level=logging.INFO, format="[harbor-bridge] %(asctime)s %(message)s")
log = logging.getLogger("harbor-bridge")

_state: dict = {
    "phase": "starting",  # starting -> ready -> finishing -> done | error
    "error": None,
    "results": None,
    "finish_requested": False,
}
_state_lock = threading.Lock()


def _set(**fields) -> None:
    with _state_lock:
        _state.update(fields)


def _get() -> dict:
    with _state_lock:
        return dict(_state)


# --------------------------------------------------------------------------
# SREGym access (everything below runs inside SREGym's own process)
# --------------------------------------------------------------------------


def _conductor():
    from sregym.conductor import conductor_api

    return getattr(conductor_api, "_conductor", None)


_sregym_module = None  # SREGym's main.py module object, captured while it runs


def _capture_sregym_module():
    """runpy installs SREGym's main.py as sys.modules['__main__'] while it runs."""
    global _sregym_module
    if _sregym_module is None:
        mod = sys.modules.get("__main__")
        if mod is not None and hasattr(mod, "LAUNCHER") and hasattr(mod, "_driver_results"):
            _sregym_module = mod
    return _sregym_module


def _launcher():
    mod = _capture_sregym_module()
    if mod is None:
        raise RuntimeError("SREGym campaign is not running")
    return mod.LAUNCHER


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [_json_safe(v) for v in value]
        return repr(value)


def _scored_snapshot() -> dict | None:
    """Stage outcomes as soon as every configured stage has been evaluated.

    SREGym only publishes its result row after cleanup (fault recovery,
    undeploy, artifact publication), which for some problems takes longer
    than the verifier budget. The stage outcomes are final once evaluated, so
    hand them to the verifier then, flattened the same way as main.py's rows.
    """
    conductor = _conductor()
    if conductor is None:
        return None
    sequence = [s["name"] for s in (getattr(conductor, "stage_sequence", None) or [])]
    results = dict(getattr(conductor, "results", {}) or {})
    if not sequence or results.get("run_status") == "incomplete":
        return None
    row = {"problem_id": os.environ.get("PROBLEM_ID")}
    for stage in sequence:
        outcome = results.get(stage.capitalize())
        if not isinstance(outcome, dict):
            return None
        for key, value in outcome.items():
            row[f"{stage.capitalize()}.{key}"] = value
    row["run_status"] = "complete"
    row["snapshot"] = "scored_before_cleanup"
    return _json_safe(row)


def _snapshot_results() -> dict | None:
    """Return the final per-attempt results, or None while still running."""
    mod = _capture_sregym_module()
    if mod is None:
        return None
    rows = []
    for entry in mod._driver_results or []:
        for agent_rows in entry.values():
            rows.extend(agent_rows)
    if rows:
        return _json_safe(rows[-1])
    return None


# --------------------------------------------------------------------------
# Readiness: kubeconfig hand-off and proxy forwarding
# --------------------------------------------------------------------------


def _bridge_kubeconfig() -> bool:
    """Copy SREGym's agent kubeconfig to the volume shared with ``main``."""
    conductor = _conductor()
    if conductor is None:
        return False
    path = conductor.get_agent_kubeconfig_path()
    if not path or not Path(path).is_file():
        return False
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    target = SHARED_DIR / "config"
    tmp = target.with_suffix(".tmp")
    shutil.copyfile(path, tmp)
    tmp.chmod(0o644)
    tmp.replace(target)
    return True


def _proxy_bind_address() -> str | None:
    """The address SREGym bound its filtering proxy to (DinD's docker bridge)."""
    conductor = _conductor()
    if conductor is None:
        return None
    host = getattr(conductor.k8s_proxy, "listen_host", None)
    return host or None


def _outer_address() -> str | None:
    """IPv4 address of the interface with the default route.

    That interface is the compose network Harbor's ``main`` container is on.
    The daemon's own bridges (docker0, the KIND network, agent networks) are
    internal to this container.
    """
    route = subprocess.run(["ip", "-4", "-o", "route", "show", "default"],
                           capture_output=True, text=True, check=False).stdout.split()
    if "dev" not in route:
        return None
    dev = route[route.index("dev") + 1]
    addrs = subprocess.run(["ip", "-4", "-o", "addr", "show", "dev", dev],
                           capture_output=True, text=True, check=False).stdout.split()
    if "inet" not in addrs:
        return None
    return addrs[addrs.index("inet") + 1].split("/")[0]


def _start_proxy_forwarders(bind_host: str) -> None:
    """Expose the proxy on the compose network, where ``main`` can reach it.

    SREGym binds the proxy to the private daemon's bridge gateway, the address
    nested agent containers use. Harbor's ``main`` container is on the outer
    compose network, so forward the same port from this container's outer
    address. Clients connect to ``host.docker.internal``, a name in the
    proxy's certificate that the compose network alias resolves here.
    """
    if bind_host in {"0.0.0.0", "::", ""}:
        return
    addr = _outer_address()
    if addr is None or addr == bind_host:
        log.warning("no outer address to forward the proxy from (bind_host=%s)", bind_host)
        return
    log.info("forwarding %s:%d -> %s:%d", addr, PROXY_PORT, bind_host, PROXY_PORT)

    def supervise() -> None:
        while True:
            proc = subprocess.Popen(
                ["socat", f"TCP-LISTEN:{PROXY_PORT},bind={addr},fork,reuseaddr", f"TCP:{bind_host}:{PROXY_PORT}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            code = proc.wait()
            log.warning("proxy forwarder exited with %s; restarting", code)
            time.sleep(1)

    threading.Thread(target=supervise, name="proxy-forwarder", daemon=True).start()


def _conductor_stage() -> str | None:
    conductor = _conductor()
    if conductor is None:
        return None
    return getattr(conductor, "submission_stage", None)


def _readiness_watcher() -> None:
    forwarded = False
    while True:
        _capture_sregym_module()
        phase = _get()["phase"]
        if phase not in {"starting"}:
            return
        stage = _conductor_stage()
        if stage in {"diagnosis", "mitigation"} and _bridge_kubeconfig():
            if not forwarded:
                bind_host = _proxy_bind_address()
                if bind_host:
                    _start_proxy_forwarders(bind_host)
                forwarded = True
            _set(phase="ready")
            READY_FILE.touch()
            log.info("problem ready at stage %s", stage)
            return
        time.sleep(2)


# --------------------------------------------------------------------------
# HTTP API
# --------------------------------------------------------------------------


def _oracle_enabled() -> bool:
    """Oracle endpoints exist only in oracle runs (operator sets SREGYM_ENABLE_ORACLE=1)."""
    return os.environ.get("HARBOR_ENABLE_ORACLE", "") == "1"


def _token_ok(handler: BaseHTTPRequestHandler) -> bool:
    if not _oracle_enabled():
        return False
    expected = os.environ.get("HARBOR_ORACLE_TOKEN", "")
    if not expected:
        return False
    supplied = handler.headers.get("X-Harbor-Oracle-Token", "")
    if not supplied:
        supplied = parse_qs(urlparse(handler.path).query).get("token", [""])[0]
    return hmac.compare_digest(supplied, expected)


_recovery: dict = {"state": "idle", "error": None}  # idle -> running -> done | failed


def _recover(problem) -> None:
    try:
        problem.recover_fault()
    except Exception as exc:
        log.error("recover_fault failed: %s", traceback.format_exc())
        with _state_lock:
            _recovery.update(state="failed", error=f"{type(exc).__name__}: {exc}")
        return
    with _state_lock:
        _recovery.update(state="done")
    log.info("recover_fault completed")


def _request_finish() -> None:
    """Stop the passive agent: the conductor then closes submissions,
    records missing stages as incomplete, and runs its normal cleanup."""
    with _state_lock:
        if _state["finish_requested"]:
            return
        _state["finish_requested"] = True
        if _state["phase"] == "ready":
            _state["phase"] = "finishing"
    try:
        mod = _capture_sregym_module()
        lock = getattr(mod, "_launcher_cleanup_lock", None)
        if lock is not None:
            with lock:
                _launcher().cleanup_agent(AGENT_NAME, timeout=5)
        else:
            _launcher().cleanup_agent(AGENT_NAME, timeout=5)
    except Exception:
        log.warning("cleanup_agent failed: %s", traceback.format_exc())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: D401 - quiet default logging
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        route = urlparse(self.path).path
        st = _get()
        if route == "/harbor/health":
            code = 200 if st["phase"] in {"ready", "finishing", "done"} else 503
            return self._send(code, {"phase": st["phase"], "stage": _conductor_stage(), "error": st["error"]})
        if route == "/harbor/result":
            if st["phase"] != "done" and st["finish_requested"]:
                early = _scored_snapshot()
                if early is not None:
                    return self._send(200, {"phase": "scored", "error": None, "results": early})
            return self._send(200, {"phase": st["phase"], "error": st["error"], "results": st["results"]})
        if route == "/harbor/oracle/recover":
            if not _token_ok(self):
                return self._send(403, {"error": "forbidden"})
            with _state_lock:
                return self._send(200, dict(_recovery))
        if route == "/harbor/oracle/root_cause":
            if not _token_ok(self):
                return self._send(403, {"error": "forbidden"})
            conductor = _conductor()
            problem = getattr(conductor, "problem", None)
            if problem is None:
                return self._send(409, {"error": "no active problem"})
            return self._send(200, {"root_cause": str(getattr(problem, "root_cause", "") or "")})
        return self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        route = urlparse(self.path).path
        if route == "/harbor/finish":
            threading.Thread(target=_request_finish, daemon=True).start()
            return self._send(202, {"phase": _get()["phase"]})
        if route == "/harbor/oracle/recover":
            if not _token_ok(self):
                return self._send(403, {"error": "forbidden"})
            conductor = _conductor()
            problem = getattr(conductor, "problem", None)
            if problem is None:
                return self._send(409, {"error": "no active problem"})
            # recover_fault() can wait minutes for workloads to become ready,
            # longer than an HTTP connection reliably stays open through
            # proxies. Run it in the background; the oracle polls
            # GET /harbor/oracle/recover.
            with _state_lock:
                if _recovery["state"] == "idle":
                    _recovery["state"] = "running"
                    threading.Thread(target=_recover, args=(problem,), daemon=True).start()
                snapshot = dict(_recovery)
            return self._send(202, snapshot)
        return self._send(404, {"error": "not found"})


def _serve() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", BRIDGE_PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()


# --------------------------------------------------------------------------
# Campaign
# --------------------------------------------------------------------------


def _write_agent_registry() -> Path:
    """A registry with only the passive ``debug`` agent, as in upstream agents.yaml."""
    path = Path("/run/harbor-agents.yaml")
    path.write_text(
        "agents:\n"
        f"  - name: {AGENT_NAME}\n"
        '    kickoff_command: "python -c \\"import signal; signal.pause()\\""\n'
        "    kickoff_workdir: .\n"
        "    kickoff_env: null\n"
        "    install_script: null\n"
        "    agent_version: null\n"
    )
    return path


def _campaign_argv() -> list[str]:
    problem = os.environ["PROBLEM_ID"]
    judge = os.environ.get("SREGYM_JUDGE_MODEL") or "gpt-5"
    argv = [
        "main.py",
        "--problem",
        problem,
        "--agent",
        AGENT_NAME,
        "--model",
        judge,
        "--judge-model",
        judge,
        "--agent-timeout",
        os.environ.get("SREGYM_AGENT_TIMEOUT", "3600"),
    ]
    if os.environ.get("SREGYM_STAGES"):
        argv += ["--stages", *os.environ["SREGYM_STAGES"].split()]
    if os.environ.get("SREGYM_PROFILE"):
        argv += ["--profile", os.environ["SREGYM_PROFILE"]]
    return argv


def _run_campaign() -> None:
    os.chdir(SREGYM_ROOT)
    sys.path.insert(0, str(SREGYM_ROOT))
    os.environ["SREGYM_AGENT_REGISTRY"] = str(_write_agent_registry())
    sys.argv = _campaign_argv()
    log.info("running: %s", " ".join(sys.argv))
    try:
        runpy.run_path(str(SREGYM_ROOT / "main.py"), run_name="__main__")
    except SystemExit as exc:
        log.info("campaign exited with %s", exc.code)
    except BaseException as exc:  # keep serving results/errors to the verifier
        log.error("campaign failed: %s", traceback.format_exc())
        _set(error=f"{type(exc).__name__}: {exc}")
    results = _snapshot_results()
    if results is None and _get()["error"] is None:
        _set(error="campaign finished without a result row")
    was_ready = READY_FILE.exists()
    _set(phase="done", results=results)
    log.info("final results: %s", json.dumps(results)[:4000] if results else None)
    if not was_ready:
        # Deployment, fault injection or preflight failed before the agent
        # stage. Exit so the container stops, the `service_healthy`
        # dependency fails and Harbor reports an environment error at once,
        # instead of running the agent against a dead conductor.
        log.error("campaign ended before the problem became ready; exiting")
        raise SystemExit(3)


def _tee_output() -> None:
    """Copy this process's stdout/stderr, and its children's, to LOG_FILE."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    original_stdout = os.dup(1)
    tee = subprocess.Popen(
        ["tee", "-a", str(LOG_FILE)],
        stdin=subprocess.PIPE,
        stdout=original_stdout,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # outlive a signal sent to this process group
    )
    os.close(original_stdout)
    os.dup2(tee.stdin.fileno(), 1)
    os.dup2(tee.stdin.fileno(), 2)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)


def main() -> None:
    _tee_output()
    for var in ("PROBLEM_ID",):
        if not os.environ.get(var):
            raise SystemExit(f"{var} is required")
    # Port check before starting a long deployment.
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("0.0.0.0", BRIDGE_PORT))
    threading.Thread(target=_serve, name="harbor-bridge-http", daemon=True).start()
    threading.Thread(target=_readiness_watcher, name="harbor-ready", daemon=True).start()
    _run_campaign()
    # Stay up so the verifier can read results; Harbor tears the stack down.
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
