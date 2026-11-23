"""Finalize and export native evidence from inside the trusted game sidecar.

Harbor runs this collect hook before tearing down the game environment. The
separate verifier needs no access to the original game, token or agent filesystem.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://localhost:8080")
    parser.add_argument("--output", type=Path, default=Path("/var/lib/balrog/result.json"))
    parser.add_argument("--request-timeout", type=float, default=100.0)
    args = parser.parse_args()
    if not math.isfinite(args.request_timeout) or args.request_timeout <= 0:
        parser.error("Export request timeout must be positive and finite")
    temporary = args.output.with_suffix(".json.tmp")
    # Collect failures are non-fatal in Harbor. Never let an old/partial export
    # survive such a failure and become an apparently valid submission.
    args.output.unlink(missing_ok=True)
    temporary.unlink(missing_ok=True)
    token = os.environ.get("RESULT_TOKEN")
    if not token:
        raise ValueError("RESULT_TOKEN is required by the game exporter")
    request = Request(args.server.rstrip("/") + "/result", headers={"Authorization": "Bearer " + token})
    with urlopen(request, timeout=args.request_timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get("finalized") is not True:
        raise ValueError("Game did not return finalized native evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Exported finalized BALROG evidence: {result.get('task_id')}")


if __name__ == "__main__":
    main()
