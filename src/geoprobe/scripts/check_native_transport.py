"""Offline two-turn model fixture; run inside a generated agent image.

This is a runtime/transport contract check, not a model score or parity run.
The fake provider alone reads the reference fixture mounted at /fixture.json.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import runpy
import sys
import threading

parser = argparse.ArgumentParser()
parser.add_argument("--serve-only", action="store_true", help="Serve the fake model to a Harbor contract trial")
parser.add_argument("--port", type=int, default=0)
args = parser.parse_args()

reference = json.loads(Path("/fixture.json").read_text())
expected_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path("/workspace/frames").glob("*.jpg"))]
requests_seen = []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        assert self.path == "/v1/chat/completions"
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert request["model"] == "offline-contract-fixture"
        images = []
        for message in request["messages"]:
            content = message.get("content")
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "image_url":
                        raw = base64.b64decode(item["image_url"]["url"].split(",", 1)[1])
                        images.append(hashlib.sha256(raw).hexdigest())
        requests_seen.append(images)
        print(json.dumps({"fixture_request": len(requests_seen), "image_hashes": images}), flush=True)
        if len(requests_seen) == 1:
            assert images == [], "First completion must precede visual observation feedback"
            code = "import primitive_api as p\nprint(p.observe())\n"
        elif len(requests_seen) == 2:
            assert images == expected_hashes, "Image bytes/order differ from the pinned transport"
            code = "import primitive_api as p\np.submit(" + repr(reference) + ")\n"
        else:
            raise AssertionError("Native episode unexpectedly requested an extra completion")
        body = json.dumps({"choices": [{"message": {"content": code}}],
                           "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(("0.0.0.0" if args.serve_only else "127.0.0.1", args.port), Handler)
if args.serve_only:
    print("Offline fixture provider ready", flush=True)
    server.serve_forever()
    raise SystemExit(0)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ["LLM_API_KEY"] = "offline-fixture-no-credentials"
os.environ["LLM_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1"
try:
    sys.argv = ["run_public.py", "--model", "offline-contract-fixture"]
    runpy.run_path("/opt/geoprobe/run_public.py", run_name="__main__")
    assert json.loads(Path("/workspace/answer.json").read_text()) == reference
    assert len(requests_seen) == 2
    report = {"scope": "offline native-loop transport fixture, not model parity",
              "model_requests": 2, "image_count": len(expected_hashes),
              "exact_image_bytes_and_order": True, "answer_preserved": True}
    print(json.dumps(report))
finally:
    server.shutdown()
    server.server_close()
