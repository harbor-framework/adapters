"""Private native runner, with a turn mailbox at the assistant's model boundary.

The runner is upstream tools.evaluate.run_case, unmodified. Its assistant HTTP
endpoint is loopback-only; the public server cannot receive user-role calls or
world/contract writes. Harbor collects evidence after stopping the main service.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import uuid


class Mailbox:
    def __init__(self):
        self.condition = threading.Condition()
        self.pending = None
        self.answer = None
        self.result = None
        self.error = None
        self.started = False

    def offer(self, request):
        with self.condition:
            if self.pending is not None:
                raise RuntimeError("Overlapping native assistant requests")
            self.pending = {"turn_id": uuid.uuid4().hex, "request": request}
            self.answer = None
            self.condition.notify_all()

    def respond(self, payload):
        with self.condition:
            if (not self.pending or self.answer is not None
                    or payload.get("turn_id") != self.pending["turn_id"]):
                raise ValueError("Stale or duplicate turn")
            # Message validation remains in the native endpoint. HTTP failures are
            # relayed too, so context overflow, retries and infra classifications
            # stay under native control.
            status = payload.get("status", 200)
            if type(status) is not int or not 200 <= status <= 599:
                raise ValueError("Invalid provider HTTP status")
            body = payload.get("body")
            if status == 200 and not isinstance(body, dict):
                raise ValueError("Expected a Chat Completions response object")
            self.answer = (status, body)
            self.condition.notify_all()

    def view(self):
        with self.condition:
            if self.error:
                return {"state": "error", "error": self.error}
            if self.result is not None:
                return {"state": "finished", "classification": self.result.get("classification")}
            if self.pending and self.answer is None:
                return {"state": "turn", **deepcopy(self.pending)}
            return {"state": "waiting"}


def send_json(handler, value, status=200):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if not 0 < length <= 64 * 1024 * 1024:
        raise ValueError("Invalid request size")
    return json.loads(handler.rfile.read(length))


def sse_chunk(body):
    choice = body["choices"][0]
    delta = deepcopy(choice["message"])
    for index, call in enumerate(delta.get("tool_calls") or []):
        call["index"] = index
    return {
        "id": body.get("id", "harbor-bridge"), "model": body.get("model"),
        "choices": [{"index": 0, "delta": delta,
                     "finish_reason": choice.get("finish_reason", "stop")}],
        "usage": body.get("usage"),
    }


def public_response(payload):
    """An agent can supply a message, never an infrastructure classification."""
    if set(payload) != {"turn_id", "message"} or not isinstance(payload["message"], dict):
        raise ValueError("Public interface accepts only an assistant message")
    return {"turn_id": payload["turn_id"], "body": {
        "choices": [{"message": payload["message"], "finish_reason": "stop"}],
    }}


class Runtime:
    def __init__(self, private, output, upstream):
        self.private = private
        self.output = Path(output)
        self.upstream = Path(upstream)
        self.mailbox = Mailbox()
        self.thread = None

    def start(self):
        with self.mailbox.condition:
            if self.mailbox.started:
                return
            self.mailbox.started = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def run(self):
        try:
            from payment.runtime.interaction.domain import register
            from tools.evaluate import run_case
            register()
            config = deepcopy(self.private["config"])
            config["agent"]["base_url"] = f"http://127.0.0.1:{self.private_port}/v1"
            config["agent"]["api_key_env"] = "BIZ_BRIDGE_UNUSED_KEY"
            config["agent"]["timeout_seconds"] = config["episode_timeout_seconds"] + 30
            config["agent"]["trust_env"] = False
            self.output.mkdir(parents=True, exist_ok=True)
            result = run_case(self.private["task_id"], config, self.output)
            with self.mailbox.condition:
                self.mailbox.result = result
                self.mailbox.pending = None
                self.mailbox.condition.notify_all()
        except Exception as exc:
            # Setup errors occur before upstream's run_case try/finally.
            with self.mailbox.condition:
                self.mailbox.error = type(exc).__name__ + ": " + str(exc)[:500]
                self.mailbox.condition.notify_all()

    def collect(self):
        # This route exists only on the loopback listener; main cannot call it.
        if self.thread:
            self.thread.join(timeout=100)
        if self.mailbox.error:
            raise RuntimeError(self.mailbox.error)
        if self.mailbox.result is None:
            raise RuntimeError("Native episode did not finalize; no score may be fabricated")
        case = self.output / (self.private["task_id"] + "__trial0")
        return {
            "schema_version": 1,
            "task_id": self.private["task_id"],
            "upstream_commit": self.private["upstream_commit"],
            "archive_sha256": self.private["archive_sha256"],
            "result": self.mailbox.result,
            "world": json.loads((case / "final_world.json").read_text("utf-8")),
        }

    def handler(self, private=False):
        runtime = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == "/health":
                    return send_json(self, {"ready": True})
                if self.path == "/turn" and not private:
                    runtime.start()
                    return send_json(self, runtime.mailbox.view())
                return send_json(self, {"error": "Not found"}, 404)

            def do_POST(self):
                try:
                    if self.path == "/collect" and private:
                        evidence = runtime.collect()
                        target = runtime.output / "evidence.json"
                        temporary = target.with_suffix(".tmp")
                        temporary.write_text(json.dumps(evidence, ensure_ascii=False, allow_nan=False), "utf-8")
                        temporary.replace(target)
                        return send_json(self, {"collected": True})
                    if self.path == "/respond" and not private:
                        payload = read_json(self)
                        runtime.mailbox.respond(public_response(payload))
                        return send_json(self, {"accepted": True})
                    if self.path == "/provider-response" and private:
                        runtime.mailbox.respond(read_json(self))
                        return send_json(self, {"accepted": True})
                    if self.path != "/v1/chat/completions" or not private:
                        return send_json(self, {"error": "Not found"}, 404)
                    request = read_json(self)
                    runtime.mailbox.offer(request)
                    box = runtime.mailbox
                    with box.condition:
                        while box.answer is None:
                            box.condition.wait(timeout=2)
                            if box.result is not None or box.error:
                                return
                        status, body = box.answer
                        box.pending = None
                        box.answer = None
                    if status != 200:
                        return send_json(self, body, status)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    wire = body.get("sse")
                    if wire is None:
                        wire = "data: " + json.dumps(sse_chunk(body)) + "\n\ndata: [DONE]\n\n"
                    self.wfile.write(wire.encode())
                    self.wfile.flush()
                except (ValueError, KeyError, TypeError) as exc:
                    send_json(self, {"error": str(exc)}, 409)
                except BrokenPipeError:
                    pass

        return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", type=Path, default=Path("/service/private.json"))
    parser.add_argument("--upstream", type=Path, default=Path("/opt/bizagentbench"))
    parser.add_argument("--output", type=Path, default=Path("/private/runs"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    sys.path[:0] = [str(args.upstream), str(args.upstream / "third_party/tau2-bench/src")]
    private = json.loads(args.private.read_text("utf-8"))
    runtime = Runtime(private, args.output, args.upstream)
    local = ThreadingHTTPServer(("127.0.0.1", 8001), runtime.handler(private=True))
    runtime.private_port = local.server_port
    threading.Thread(target=local.serve_forever, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", args.port), runtime.handler()).serve_forever()


if __name__ == "__main__":
    main()
