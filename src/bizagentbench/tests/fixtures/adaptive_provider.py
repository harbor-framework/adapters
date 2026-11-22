"""Local native-runner fixture: adaptive assistant and scripted variable customer."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import sys
import threading

sys.path.insert(0, os.environ.get('BIZ_ADAPTIVE_SOURCE') or str(Path(__file__).resolve().parents[2] / 'src'))
from bizagentbench.adaptive import AdaptiveController
from adaptive_customer import NativeCustomerDriver


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with self.server.lock:
            if key in self.server.cache:
                message = self.server.cache[key]
            elif request['model'] == 'adaptive-agent':
                message = self.server.controller.next(request)
                self.server.cache[key] = message
            elif request['model'] == 'adaptive-user':
                message = self.server.customer.next(request)
                self.server.cache[key] = message
            else:
                raise ValueError('Only offline fixture model names are allowed')
        message = json.loads(json.dumps(message))
        for i, call in enumerate(message.get('tool_calls', [])): call['index'] = i
        chunk = {'id': 'offline-adaptive', 'model': request['model'],
                 'choices': [{'index': 0, 'delta': message, 'finish_reason': 'stop'}],
                 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
        self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
        self.wfile.write(('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode())


def server(task_id, variant='baseline', port=0):
    result = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    result.controller = AdaptiveController(task_id)
    result.customer = NativeCustomerDriver(variant)
    result.lock = threading.Lock(); result.cache = {}
    return result


if __name__ == '__main__':
    server(os.environ['BIZ_TASK_ID'], os.environ.get('BIZ_VARIANT', 'baseline'), 9000).serve_forever()
