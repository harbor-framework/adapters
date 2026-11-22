import json
import os
import signal
import sys
import time
from pathlib import Path


def wait_for_seal(path: Path, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("sealed") is True:
                return True
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def main() -> int:
    state_path = Path(os.environ.get("AGENTCLINIC_STATE_PATH", "/root/logs/consultation_state.json"))
    os.kill(int(os.environ.get("AGENTCLINIC_SERVER_PID", "1")), signal.SIGUSR1)
    return 0 if wait_for_seal(state_path) else 1


if __name__ == "__main__":
    sys.exit(main())
