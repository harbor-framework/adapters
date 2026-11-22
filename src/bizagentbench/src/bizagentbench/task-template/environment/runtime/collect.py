"""Invoked by Harbor in the sidecar after stopping the agent container."""
from pathlib import Path
from urllib.request import Request, urlopen

target = Path("/private/runs/evidence.json")
target.unlink(missing_ok=True)
with urlopen(Request("http://127.0.0.1:8001/collect", data=b"{}",
                     headers={"Content-Type": "application/json"}), timeout=105) as response:
    if response.status != 200:
        raise RuntimeError("Native evidence collection failed")
if not target.is_file():
    raise RuntimeError("Native evidence was not exported")
