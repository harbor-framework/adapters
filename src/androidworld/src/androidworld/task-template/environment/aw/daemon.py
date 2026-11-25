"""In-container AndroidWorld daemon.

Holds the AndroidWorld `env` and the instantiated task object (many `is_successful`
implementations depend on state captured during `initialize_task`, so init and scoring
must happen in the same process). Endpoints (localhost:5000):
  GET  /ready   -> 200 once the emulator is up and task.initialize_task() has finished
  POST /score   -> {"score": float}  (runs task.is_successful; reads /workspace/answer.txt
                   into env.interaction_cache for answer-style tasks)
  POST /oracle  -> runs the reference (UI-free) solution from oracles.py
"""
import base64
import json
import os
import pickle
import shutil
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SPEC = json.loads(Path("/opt/aw/task_spec.json").read_text())
ANSWER_FILE = Path("/workspace/answer.txt")
APPS_MARKER = Path("/opt/aw/.apps_ready")
STATE = {"ready": False, "error": None, "env": None, "task": None}
LOCK = threading.Lock()


def _build_task():
    # NB: information-retrieval classes are created dynamically (cls.__module__ == "abc"),
    # so look classes up through the upstream registry rather than by module path.
    from android_world import registry

    cls = registry.TaskRegistry().get_registry("android_world")[SPEC["name"]]
    params = pickle.loads(base64.b64decode(SPEC["params_pickle_b64"]))
    return cls(params)


def _init():
    try:
        from android_world.env import env_launcher

        first = not APPS_MARKER.exists()
        sdk_root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or "/opt/android"
        adb_path = shutil.which("adb") or os.path.join(sdk_root, "platform-tools", "adb")
        env = env_launcher.load_and_setup_env(
            console_port=5554,
            emulator_setup=first,
            freeze_datetime=True,
            adb_path=adb_path,
        )
        if first:
            APPS_MARKER.touch()
        task = _build_task()
        assert task.goal == SPEC["goal"], "goal mismatch vs. exported spec"
        task.initialize_task(env)
        STATE.update(env=env, task=task, ready=True)
        print("[aw-daemon] ready", flush=True)
    except Exception:  # noqa: BLE001
        STATE["error"] = traceback.format_exc()
        print(STATE["error"], file=sys.stderr, flush=True)


def _score():
    env, task = STATE["env"], STATE["task"]
    if SPEC.get("answer_task"):
        env.interaction_cache = (
            ANSWER_FILE.read_text().strip() if ANSWER_FILE.exists() else ""
        )
    return float(task.is_successful(env))


def _oracle():
    if "/opt/aw" not in sys.path:
        sys.path.insert(0, "/opt/aw")
    import oracles

    return oracles.run(STATE["env"], STATE["task"], SPEC)


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/ready":
            if STATE["error"]:
                return self._send(500, {"error": STATE["error"]})
            return self._send(200 if STATE["ready"] else 503, {"ready": STATE["ready"]})
        self._send(404, {})

    def do_POST(self):  # noqa: N802
        if not STATE["ready"]:
            return self._send(503, {"error": STATE["error"] or "not ready"})
        try:
            with LOCK:
                if self.path == "/score":
                    return self._send(200, {"score": _score()})
                if self.path == "/oracle":
                    return self._send(200, {"result": _oracle()})
        except Exception:  # noqa: BLE001
            return self._send(500, {"error": traceback.format_exc()})
        self._send(404, {})

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    threading.Thread(target=_init, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", 5000), H).serve_forever()
