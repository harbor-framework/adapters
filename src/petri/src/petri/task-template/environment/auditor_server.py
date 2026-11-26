"""
Petri auditor.

Runs Petri's auditor from inspect_petri against the target.

The Inspect log is written to LOG_DIR, which is collected as an artifact for the verifier.

Endpoints:
  GET  /health  - healthcheck
  POST /start   - start the audit
  POST /reply   - deliver the target's reply
"""

import json
import os
import queue
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
from inspect_ai import Task, eval as inspect_eval
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ModelOutput
from inspect_petri import audit_solver, audit_viewer, auditor_agent, auditor_tools, seeds_dataset
from inspect_petri.target import TOOL_RESULT, ExitSignal, TargetContext

PORT = 8000
SEED_DIR = "/app/environment"
LOG_DIR = "/app/logs"

AUDITOR_MODEL = os.environ["AUDITOR_MODEL"]
REPLY_TIMEOUT_SEC = float(os.environ.get("REPLY_TIMEOUT_SEC", "900"))
TARGET_MODEL_PLACEHOLDER = "mockllm/model"
TARGET_NAME = "assistant"

MAX_TURNS = 30
ENABLE_ROLLBACK = False

_to_target: queue.Queue[list[dict]] = queue.Queue()
_from_target: queue.Queue[str | None] = queue.Queue()

_started = False
_start_lock = threading.Lock()


def _wait_for_reply() -> str | None:
    try:
        return _from_target.get(timeout=REPLY_TIMEOUT_SEC)
    except queue.Empty:
        return None


@agent(name="target")
def http_target() -> Agent:
    """Petri target driver whose `model` is the agent communicating with chat.py."""
    async def execute(state: AgentState, context: TargetContext) -> AgentState:
        try:
            # Get system prompt and first user message from auditor
            await context.wait_for_resume()
            system_message = await context.system_message()
            user_message = await context.user_message()

            # Set system prompt and first user message
            state.messages[:] = [system_message, user_message]
            _to_target.put(
                [
                    { "role": "system", "content": system_message.text },
                    { "role": "user", "content": user_message.text },
                ]
            )

            while True:
                # Get reply from target
                reply = await anyio.to_thread.run_sync(_wait_for_reply)
                if reply is None:
                    return state

                output = ModelOutput.from_content(model="target", content=reply)
                state.output = output
                state.messages.append(output.message)

                # Send reply to auditor
                context.expect({TOOL_RESULT: set()})
                await context.send_output(output)
                user_message = await context.user_message()

                state.messages.append(user_message)
                _to_target.put([{ "role": "user", "content": user_message.text }])
        except ExitSignal:
            return state

    return execute


def _run_audit() -> None:
    try:
        # Run audit with auditor and target
        task = Task(
            dataset=seeds_dataset(SEED_DIR),
            solver=audit_solver(
                auditor=auditor_agent(
                    max_turns=MAX_TURNS,
                    tools=auditor_tools(
                        prefill=False,
                        rollback=ENABLE_ROLLBACK,
                        target_tools="none",
                    ),
                    target_display_name=TARGET_NAME,
                ),
                target=http_target(),
            ),
            viewer=audit_viewer(),
        )

        inspect_eval(
            task,
            model=AUDITOR_MODEL,
            model_roles={"auditor": AUDITOR_MODEL, "target": TARGET_MODEL_PLACEHOLDER},
            log_dir=LOG_DIR,
            display="none",
        )
    except Exception as e:
        print(f"Audit failed: {e!r}", flush=True)
    finally:
        _to_target.put([{ "done": True }])


def _start_audit() -> None:
    global _started

    with _start_lock:
        if not _started:
            _started = True
            threading.Thread(target=_run_audit, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/health":
            self._json(200, { "ok": True })
        else:
            self._json(404, { "error": "not found" })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/start":
            _start_audit()
            self._json(200, { "events": _to_target.get() })
        elif self.path == "/reply":
            _from_target.put(body.get("reply", ""))
            self._json(200, { "events": _to_target.get() })
        else:
            self._json(404, { "error": "not found" })

    def _json(self, code, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: _from_target.put(None))
    print(f"auditor_server ready on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
