"""Trusted host relay's local entry point, never copied into the agent image."""
from pathlib import Path
import sys
from urllib.request import Request, urlopen

path = Path(sys.argv[1])
if path.parent != Path("/private") or not path.name.startswith("relay-"):
    raise ValueError("Unexpected private relay path")
with urlopen(Request("http://127.0.0.1:8001/provider-response", data=path.read_bytes(),
                     headers={"Content-Type": "application/json"}), timeout=15) as response:
    if response.status != 200:
        raise RuntimeError("Native provider response rejected")
