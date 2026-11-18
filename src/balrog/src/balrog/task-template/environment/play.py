"""Interact with the BabyAI game service without access to its private state."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(server, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(server.rstrip("/") + path, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=os.environ.get("BALROG_SERVER", "http://game:8080"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("observe")
    act = commands.add_parser("act")
    act.add_argument("action")
    act.add_argument("--expected-step", type=int)
    args = parser.parse_args()
    try:
        if args.command == "observe":
            result = request(args.server, "/observation")
        else:
            step = args.expected_step
            if step is None:
                step = request(args.server, "/observation")["step"]
            result = request(args.server, "/action", {"action": args.action, "expected_step": step})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        print(f"Game request failed ({exc.code}): {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
    except (URLError, OSError, ValueError, KeyError) as exc:
        print(f"Game request failed: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
