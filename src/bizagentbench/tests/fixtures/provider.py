"""Deterministic SSE provider for transport tests, never a benchmark oracle."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = request["model"]
        if model == "offline-http-error":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"offline credential failure"}')
            return
        if model == "offline-user":
            previous = any(item.get("content") == "Please help me with my payment." for item in request["messages"])
            message = {"content": "###STOP###" if previous else "Please help me with my payment."}
        elif model == "offline-bad-user":
            message = {"tool_calls": [{"id": "bad", "type": "function", "function": {
                "name": "get_my_requests", "arguments": "{invalid-json"}}]}
        elif any(item.get("role") == "tool" for item in request["messages"]):
            message = {"content": "I cannot complete this payment. Goodbye."}
        else:
            message = {"tool_calls": [{"id": "clock", "type": "function", "function": {
                "name": "get_clock", "arguments": "{}"}}]}
        for index, call in enumerate(message.get("tool_calls", [])):
            call["index"] = index
        chunk = {"id": "offline", "model": model, "choices": [{"index": 0, "delta": message,
                    "finish_reason": "stop"}], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode())


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
