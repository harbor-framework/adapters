#!/usr/bin/env python3
"""fm: command-line client for the FM-Bench game server.

  fm packet                      show the current decision stop
  fm tools                       list the 26 tools and their argument schemas
  fm call <tool> ['<json args>'] call a tool, e.g.  fm call get_squad
                                 fm call set_tactics '{"formation": "4-3-3"}'
  fm advance                     end this stop; prints the next stop packet
"""

import json
import os
import sys
import urllib.request

SERVER = os.environ.get("FM_SERVER", "http://game:8080")
TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools.json")


def http(path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(SERVER + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "packet":
        out = http("/packet")
    elif cmd == "tools":
        out = json.load(open(TOOLS, encoding="utf-8"))
    elif cmd == "advance":
        out = http("/tool", {"name": "advance", "args": {}})
    elif cmd == "rpc" and len(argv) == 3:
        # machine interface for harness agents: one base64-encoded JSON
        # request {"name", "args"} in, one compact JSON envelope out
        import base64
        body = json.loads(base64.b64decode(argv[2]))
        out = http("/packet") if body["name"] == "packet" else http("/tool", body)
        print(json.dumps(out))
        return 0
    elif cmd == "call" and len(argv) >= 3:
        try:
            args = json.loads(argv[3]) if len(argv) > 3 else {}
        except ValueError as e:
            print(f"arguments must be one JSON object: {e}", file=sys.stderr)
            return 2
        out = http("/tool", {"name": argv[2], "args": args})
    else:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
