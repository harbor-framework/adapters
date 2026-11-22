"""Replay assistant turns only; the live native user still handles approvals."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, "/app")
from biz import call

messages = iter(json.loads(Path(sys.argv[1]).read_text("utf-8")))
seen = set()
while True:
    turn = call("/turn")
    if turn["state"] == "finished":
        break
    if turn["state"] == "error":
        raise RuntimeError(turn["error"])
    if turn["state"] != "turn" or turn["turn_id"] in seen:
        time.sleep(0.1)
        continue
    seen.add(turn["turn_id"])
    try:
        message = next(messages)
    except StopIteration:
        raise RuntimeError("Reference exhausted before native stop")
    call("/respond", {"turn_id": turn["turn_id"], "message": message})
