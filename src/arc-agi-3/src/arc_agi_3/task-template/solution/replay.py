"""Replay a reference trajectory through the same public action API as the agent."""

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def replay(path, runtime_url):
    if not path.exists():
        raise FileNotFoundError(f"No validated oracle trajectory is available: {path}")
    trajectory = json.loads(path.read_text())

    def request(route, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(
            f"{runtime_url.rstrip('/')}/{route}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=120) as response:
            result = json.load(response)
        if result.get("ok") is not True:
            raise RuntimeError(result)
        return result

    health = request("health")
    if health.get("game_id") != trajectory["game_id"]:
        raise ValueError("Oracle and runtime game IDs differ")
    if request("progress")["total_actions"] != 0:
        raise ValueError("Oracle requires a fresh runtime")
    for action in trajectory["actions"]:
        request("action", action)
    progress = request("progress")
    if progress["state"] != "win":
        raise RuntimeError(f"Oracle did not win: {progress}")
    print(json.dumps(progress))
    return progress


if __name__ == "__main__":
    replay(Path(sys.argv[1]), os.environ.get("ARC_RUNTIME_API_BASE", "http://game:8000"))
