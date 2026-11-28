"""
Thin proxy between the agent and the user.

`python3 chat.py` prints the current messages and starts the conversation.
`python3 chat.py --reply` reads the reply from stdin, sends it, then prints the resulting user message.

Each printed line is the user's next event as JSON: { "role": "system" | "user", "content": "..." } or { "done": true }.
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


try:
    if "--reply" in sys.argv:
        response = post("/reply", { "reply": sys.stdin.read().strip() })
    else:
        response = post("/start", {})
except urllib.error.HTTPError as e:
    print(json.dumps({ "error": e.read().decode() }), flush=True)
    sys.exit(1)

for event in response["events"]:
    print(json.dumps(event), flush=True)
