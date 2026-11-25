"""Container-side bridge exposing AndroidWorld AsyncEnv over localhost HTTP.

Uploaded into the task container by ``T3AAgent.setup`` and run using the
container's system Python where ``android_world`` is installed.
Must NOT import ``harbor`` or third-party host packages.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TASK_SPEC_PATH = Path("/opt/aw/task_spec.json")
ANSWER_FILE = Path("/workspace/answer.txt")
DEFAULT_PORT = 5001
DEFAULT_HOST = "127.0.0.1"

_LOCK = threading.Lock()
_ENV: Any = None
_SPEC: dict[str, Any] = {}


def _resolve_adb_path() -> str:
    sdk_root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or "/opt/android"
    return shutil.which("adb") or os.path.join(sdk_root, "platform-tools", "adb")


def _load_task_spec() -> dict[str, Any]:
    if TASK_SPEC_PATH.exists():
        return json.loads(TASK_SPEC_PATH.read_text(encoding="utf-8"))
    return {}


def _get_env() -> Any:
    global _ENV
    if _ENV is None:
        from android_world.env import env_launcher

        _ENV = env_launcher.load_and_setup_env(
            console_port=5554,
            emulator_setup=False,
            freeze_datetime=False,
            adb_path=_resolve_adb_path(),
        )
    return _ENV


def _post_transition_state(env: Any, transition_pause: float | None) -> Any:
    if transition_pause is None:
        return env.get_state(wait_to_stabilize=True)
    time.sleep(float(transition_pause))
    return env.get_state(wait_to_stabilize=False)


def _save_pixels(pixels: Any, save_path: str | None) -> str | None:
    if not save_path or pixels is None:
        return None
    from PIL import Image

    out = Path(save_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(out, format="PNG")
    return str(out)


def _state_payload(
    env: Any,
    *,
    transition_pause: float | None,
    save_screenshot_path: str | None,
) -> dict[str, Any]:
    from android_world.agents import t3a

    state = _post_transition_state(env, transition_pause)
    logical_screen_size = env.logical_screen_size
    ui_elements = state.ui_elements
    description = t3a._generate_ui_elements_description_list_full(  # noqa: SLF001
        ui_elements,
        logical_screen_size,
    )
    saved_path = _save_pixels(state.pixels, save_screenshot_path)
    return {
        "ui_elements_description": description,
        "num_ui_elements": len(ui_elements),
        "logical_screen_size": list(logical_screen_size),
        "screenshot_path": saved_path,
    }


def _handle_reset(body: dict[str, Any]) -> dict[str, Any]:
    global _SPEC
    _SPEC = _load_task_spec()
    env = _get_env()
    go_home = bool(body.get("go_home", True))
    env.reset(go_home=go_home)
    env.hide_automation_ui()
    return {"ok": True, "task_spec": _SPEC}


def _handle_state(body: dict[str, Any]) -> dict[str, Any]:
    env = _get_env()
    return _state_payload(
        env,
        transition_pause=body.get("transition_pause"),
        save_screenshot_path=body.get("save_screenshot_path"),
    )


def _handle_execute(body: dict[str, Any]) -> dict[str, Any]:
    from android_world.env import json_action

    env = _get_env()
    action_dict = body.get("action") or {}
    converted = json_action.JSONAction(**action_dict)

    if converted.action_type == "answer":
        ANSWER_FILE.parent.mkdir(parents=True, exist_ok=True)
        ANSWER_FILE.write_text(converted.text or "", encoding="utf-8")

    env.execute_action(converted)

    after_payload = _state_payload(
        env,
        transition_pause=body.get("transition_pause"),
        save_screenshot_path=body.get("save_screenshot_path"),
    )
    return {
        "ok": True,
        "after_element_list": after_payload["ui_elements_description"],
        "num_ui_elements": after_payload["num_ui_elements"],
        "logical_screen_size": after_payload["logical_screen_size"],
        "screenshot_path": after_payload["screenshot_path"],
    }


class _BridgeHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            with _LOCK:
                spec = _SPEC or _load_task_spec()
                return self._send(200, {"ok": True, "task_spec": spec})
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            return self._send(400, {"error": f"invalid json: {exc}"})

        try:
            with _LOCK:
                if self.path == "/reset":
                    return self._send(200, _handle_reset(body))
                if self.path == "/state":
                    return self._send(200, _handle_state(body))
                if self.path == "/execute":
                    return self._send(200, _handle_execute(body))
        except Exception:  # noqa: BLE001
            return self._send(500, {"error": traceback.format_exc()})
        self._send(404, {"error": "not found"})

    def log_message(self, *args: Any) -> None:
        pass


def _serve(host: str, port: int) -> int:
    with _LOCK:
        _load_task_spec()
        _get_env()
    server = ThreadingHTTPServer((host, port), _BridgeHandler)
    print(f"[t3a-env-bridge] listening on {host}:{port}", flush=True)
    server.serve_forever()
    return 0


def _call(
    host: str,
    port: int,
    endpoint: str,
    method: str,
    payload: str | None,
    timeout: int,
) -> int:
    url = f"http://{host}:{port}{endpoint}"
    data = None if method == "GET" else (payload or "{}").encode("utf-8")
    headers = {} if method == "GET" else {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            sys.stdout.write(resp.read().decode("utf-8"))
            sys.stdout.flush()
            return 0
    except urllib.error.HTTPError as exc:
        sys.stderr.write(exc.read().decode("utf-8", errors="replace"))
        sys.stderr.flush()
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default=DEFAULT_HOST)
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)

    p_call = sub.add_parser("call")
    p_call.add_argument("--host", default=DEFAULT_HOST)
    p_call.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_call.add_argument("--endpoint", required=True)
    p_call.add_argument("--method", choices=["GET", "POST"], default="POST")
    p_call.add_argument("--payload", default="{}")
    p_call.add_argument("--timeout", type=int, default=120)

    args = parser.parse_args()
    if args.cmd == "serve":
        return _serve(args.host, args.port)
    return _call(args.host, args.port, args.endpoint, args.method, args.payload, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
