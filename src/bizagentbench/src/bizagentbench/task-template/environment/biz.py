"""Public turn client; contains no benchmark assets or grader logic."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def call(path, payload=None):
    request = Request("http://business:8000" + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("turn")
    respond = sub.add_parser("respond")
    respond.add_argument("--turn-id", required=True)
    respond.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "turn":
        result = call("/turn")
    else:
        message = json.loads(args.file.read_text("utf-8"))
        result = call("/respond", {"turn_id": args.turn_id, "message": message})
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
