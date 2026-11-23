#!/usr/bin/env python3
"""FM-Bench game sidecar.

Holds the engine and the world. The agent container reaches the game only
through this HTTP API, which forwards to Game.call_tool: the same single
read path (engine/obs) and write path (engine/actions), with the same per-stop
query and offer budgets, as the original harness. Nothing here returns true
player ability, the seed, or engine state.

Endpoints:
  GET  /health             liveness probe
  GET  /packet             the current decision-stop packet
  POST /tool               {"name": ..., "args": {...}} -> the tool envelope
                           (name "advance" ends the stop and returns the next packet)
  GET  /result?token=...   verifier only: settle the run and return the score
  GET  /actions?token=...  verifier only: the action log of the run so far. With
                           the seed it replays to the same final state, so a
                           trial's score can be checked without the container.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from engine.game import Game

# Inside the sidecar the server must listen on every interface, or the agent
# container cannot reach it over the compose network; the compose file
# publishes no port to the host. Run on a host, set FM_HOST=127.0.0.1.
HOST = os.environ.get("FM_HOST", "0.0.0.0")
PORT = int(os.environ.get("FM_PORT", "8080"))
SEED = int(os.environ["FM_SEED"])
YEARS = int(os.environ.get("FM_YEARS", "20"))
REFERENCE = float(os.environ["FM_REFERENCE"])
RESULT_TOKEN = os.environ["RESULT_TOKEN"]
# the official Solo configuration (the param_overrides stamped in the paper's
# run manifests): equal-endowment draft, sealed bids, 5/5/5 opponents, revival
OVERRIDES = {"draft": {"enabled": True}, "market_ai": {"sealed_bids": True},
             "opponents": {"tier_mix": "555"}, "revival": {"enabled": True}}

# one game per container; the lock makes every request see a consistent state
_lock = threading.Lock()
_game = Game(seed=SEED, years=YEARS, player_club="mid", param_overrides=OVERRIDES)
_packet = _game.start()
_result: dict | None = None  # set once the run is settled; no tool call after that


def _call(name: str, args: dict) -> dict:
    """One tool call, exactly as the original harness makes it."""
    global _packet
    env = _game.call_tool(name, args)
    if name == "advance" and env.get("ok"):
        _packet = env["data"]
    return env


def _settle() -> dict:
    """Score the run. An unfinished run settles as abandoned, which the
    original scorer discounts (rho); a finished one is scored as is."""
    global _result
    if _result is None:
        r = _game.final_result()
        s = float(r["s_final"])
        _result = {
            "reward": max(0.0, min(1.0, s / REFERENCE)),
            "s_final": s,
            "reference": REFERENCE,
            "settle_reason": r["settle_reason"],
            "death_count": r["death_count"],
            "channels": r["channels"],
            "final_state_hash": r["final_state_hash"],
            "stops_total": r["stops_total"],
        }
    return _result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/health":
            return self._json(200, {"ok": True})
        if url.path == "/packet":
            with _lock:
                return self._json(200, _packet)
        if url.path in ("/result", "/actions"):
            if parse_qs(url.query).get("token", [""])[0] != RESULT_TOKEN:
                return self._json(403, {"error": "forbidden"})
            with _lock:
                if url.path == "/result":
                    return self._json(200, _settle())
                return self._json(200, list(_game.action_log or []))
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/tool":
            return self._json(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            name = body["name"]
            args = body.get("args") or {}
            if not isinstance(name, str) or not isinstance(args, dict):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return self._json(400, {"error": 'body must be {"name": str, "args": object}'})
        with _lock:
            if _result is not None:
                return self._json(200, {"ok": False, "error": {
                    "code": "game_over", "hint": "the run has been settled"}})
            return self._json(200, _call(name, args))

    def _json(self, code: int, data) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_):
        pass  # no access log: one line per tool call would flood the container log


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
