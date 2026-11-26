"""
Thin proxy between the agent and the user.

Run this script and feed it one JSON reply per line on stdin, e.g.:
    { "reply": "Hello! How can I help?" }

Each line printed back on stdout is the user's next event as JSON:
    { "role": "system" | "user", "content": "..." } or { "done": true }
"""

import json
import sys
import time
import urllib.error
import urllib.request

SERVER = "http://user:8000"


def get(path):
    with urllib.request.urlopen(f"{SERVER}{path}") as r:
        return json.loads(r.read())


def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SERVER}{path}",
        data=body,
        headers={ "Content-Type": "application/json" },
    )

    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


# Wait for the server to be ready
for _ in range(300):
    try:
        get("/health")
        break
    except urllib.error.URLError:
        time.sleep(1)


def emit(events):
    """Print each event and return True if the conversation is done."""
    for event in events:
        print(json.dumps(event), flush=True)

    return any(event.get("done") for event in events)


if emit(post("/start", {})["events"]):
    sys.exit(0)

for line in sys.stdin:
    line = line.strip()

    if not line:
        continue

    try:
        reply = json.loads(line)["reply"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(json.dumps({"error": f"invalid reply: {e}"}), flush=True)
        continue

    try:
        events = post("/reply", { "reply": reply })["events"]
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": e.read().decode()}), flush=True)
        continue

    if emit(events):
        break
