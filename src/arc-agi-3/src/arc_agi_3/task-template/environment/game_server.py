"""
ARC-AGI-3 game.

Runs the actual game object and provides an HTTP API so the agent
container can play the game without being able to write the result.

Every action is added to the agent's actions log that the agent
does not have access to. The verifier will use this log to replay
the entire game and determine whether the agent won or not.

Endpoints:
  GET  /health       - healthcheck
  GET  /observation  - current frame data
  POST /action       - perform one action and returns frame data
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from arcengine import ActionInput
from __MODULE__ import __CLASS_NAME__

PORT = 8000
ACTIONS_LOG_PATH = Path("/app/actions.jsonl")

_game = __CLASS_NAME__()
_frame = _game.perform_action(ActionInput(id=0))  # RESET: establishes the first frame
_actions_log = ACTIONS_LOG_PATH.open("a")


def _serialize(frame_data):
    return {
        "game_id": frame_data.game_id,
        "frame": frame_data.frame,
        "state": frame_data.state.value,
        "levels_completed": frame_data.levels_completed,
        "win_levels": frame_data.win_levels,
        "available_actions": frame_data.available_actions,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/health":
            self._json(200, { "ok": True })
        elif path == "/observation":
            self._json(200, _serialize(_frame))
        else:
            self._json(404, { "error": "not found" })

    def do_POST(self):
        global _frame

        if self.path != "/action":
            self._json(404, { "error": "not found" })
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        try:
            action = ActionInput(**body)
        except Exception as e:
            self._json(400, { "error": str(e) })
            return

        try:
            _frame = _game.perform_action(action)
        except Exception as e:
            self._json(400, { "error": str(e) })
            return

        _actions_log.write(json.dumps(body) + "\n")
        _actions_log.flush()

        self._json(200, _serialize(_frame))

    def _json(self, code, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"game_server: __MODULE__ ready on :{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
