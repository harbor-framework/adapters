"""Scripted positive control through native tools, not live-model oracle evidence."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading


def messages_from_trace(trace, opening="Please help complete the business request described in my customer instructions.", dialogue=()):
    assistant, user = [], [{"content": opening}]
    for exchange in dialogue:
        assistant.append({'content': exchange['question']})
        user.append({'content': exchange['answer']})
    previous = None
    pending = None
    customer_receipts = []
    for index, row in enumerate(trace):
        actor = row["actor"]
        if row['tool'] == 'call_discoverable_agent_tool':
            pending = row['arguments']
        if actor == "user" and previous == "assistant":
            if row["tool"] == "get_my_requests":
                assistant.append({"content": "Please review this exact business proposal in your portal and approve it if it agrees with your requirements: " + json.dumps(pending)})
            elif row['tool'] == 'wait_for_update':
                assistant.append({"content": "Please press your bank portal's wait/update button once to request the next actual bank update, and tell me the receipt."})
            elif row['tool'] == 'list_my_files':
                assistant.append({'content': 'Please check your available supporting files and tell me what your portal shows.'})
            elif row['tool'] == 'upload_file':
                assistant.append({'content': 'Please upload the supporting document to the specified business target: ' + json.dumps(row['arguments'])})
            else:
                assistant.append({'content': 'Please complete this portal action and report its receipt: ' + json.dumps({'tool': row['tool'], **row['arguments']})})
        if actor == "assistant" and previous == "user":
            user.append({"content": "My portal returned these results: " + json.dumps(customer_receipts)})
            customer_receipts = []
        if actor == 'user':
            customer_receipts.append({'tool': row['tool'], 'result': row['response']})
        message = {"tool_calls": [{"id": f"reference-{actor}-{index}", "type": "function", "function": {
            "name": row["tool"], "arguments": json.dumps(row["arguments"])}}]}
        (assistant if actor == "assistant" else user).append(message)
        previous = actor
    outcomes = [row for row in trace if row['actor'] == 'assistant' and row['tool'] == 'record_case_outcome']
    assistant.append({"content": outcomes[-1]['arguments']['summary'] if outcomes else 'The scripted tool sequence has ended.'})
    user.append({"content": "Thank you. ###STOP###"})
    return {"reference-agent": iter(assistant), "reference-user": iter(user)}, assistant


class ReferenceHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.server.plan_lock:
            try:
                message = next(self.server.plans[request["model"]])
            except (KeyError, StopIteration):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"reference script exhausted"}')
                return
        message = json.loads(json.dumps(message))
        for index, call in enumerate(message.get("tool_calls", [])):
            call["index"] = index
        chunk = {"id": "scripted-reference", "model": request["model"],
                 "choices": [{"index": 0, "delta": message, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode())


def server(trace, port=0, opening="Please help complete the business request described in my customer instructions.", dialogue=()):
    result = ThreadingHTTPServer(("0.0.0.0", port), ReferenceHandler)
    result.plans, _ = messages_from_trace(trace, opening, dialogue)
    result.plan_lock = threading.Lock()
    return result


if __name__ == "__main__":
    context = json.loads(Path('/customer-context.json').read_text('utf-8'))
    server(json.loads(Path("/public-tools.json").read_text("utf-8")), 9000, context['opening'], context.get('dialogue', ())).serve_forever()
