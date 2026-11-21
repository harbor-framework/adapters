"""Deterministic Anthropic HTTP responses for offline tests, never real inference."""
import json


class FakeAnthropic:
    def __init__(self, scenario, answer="b1c3"):
        self.scenario, self.answer = scenario, answer
        self.requests = []
        self.generations = 0

    def response(self, path, body):
        self.requests.append({"path": path, "body": body})
        if path != "/v1/messages":
            # Local mode must work even when every count request would fail.
            return 503, {"content-type": "application/json"}, json.dumps({
                "type": "error", "error": {"type": "api_error", "message": "count unavailable"}
            }).encode()
        if self.scenario == "error":
            return 400, {"content-type": "application/json"}, json.dumps({
                "type": "error", "error": {"type": "invalid_request_error", "message": "offline error"}
            }).encode()
        self.generations += 1
        is_summary = not body.get("tools")
        stop, tokens = "tool_use", 10
        blocks = [{"type": "tool_use", "id": "toolu_test", "name": "submit_answer",
                   "input": {"answer": self.answer}}]
        if is_summary:
            blocks = [{"type": "text", "text": "The position has been analyzed. Submit the move."}]
            stop = "end_turn"
        elif self.generations == 1 and self.scenario in ("continue", "forced", "compact"):
            blocks = [
                {"type": "thinking", "thinking": "Consider checks and captures.", "signature": "offline-signature"},
                {"type": "text", "text": "Consider the rook and king. " * (2000 if self.scenario == "compact" else 1)},
            ]
            stop = "max_tokens"
        message = {"id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
                   "content": blocks, "stop_reason": stop, "stop_sequence": None,
                   "usage": {"input_tokens": 100, "output_tokens": tokens,
                             "cache_read_input_tokens": 20, "cache_creation_input_tokens": 30}}
        if not body.get("stream"):
            return 200, {"content-type": "application/json"}, json.dumps(message).encode()
        events = [{"type": "message_start", "message": {**message, "content": [], "stop_reason": None,
                    "usage": {**message["usage"], "output_tokens": 0}}}]
        for index, block in enumerate(blocks):
            # Empty blocks plus deltas exercise SDK parsing and thinking replay.
            if block["type"] == "tool_use":
                initial = {**block, "input": {}}
                deltas = [{"type": "input_json_delta", "partial_json": json.dumps(block["input"])}]
            elif block["type"] == "thinking":
                initial = {"type": "thinking", "thinking": "", "signature": ""}
                deltas = [{"type": "thinking_delta", "thinking": block["thinking"]},
                          {"type": "signature_delta", "signature": block["signature"]}]
            else:
                initial = {"type": "text", "text": ""}
                deltas = [{"type": "text_delta", "text": block["text"]}]
            events.append({"type": "content_block_start", "index": index, "content_block": initial})
            events.extend({"type": "content_block_delta", "index": index, "delta": d} for d in deltas)
            events.append({"type": "content_block_stop", "index": index})
        events.extend([
            {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
             "usage": {"output_tokens": tokens}},
            {"type": "message_stop"},
        ])
        payload = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
        return 200, {"content-type": "text/event-stream"}, payload.encode()
