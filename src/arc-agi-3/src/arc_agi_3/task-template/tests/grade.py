"""
Grades an ARC-AGI-3 game session.

Replays the agent's actions log with a new instance of the game.

Reward is 1.0 if the replayed game results in a win state, and 0.0 otherwise.
"""

import json
from pathlib import Path

from arcengine import ActionInput
from __MODULE__ import __CLASS_NAME__

ACTIONS_LOG_PATH = Path("/app/actions.jsonl")
REWARD_PATH = Path("/logs/verifier/reward.txt")


def main() -> int:
    game = __CLASS_NAME__()
    frame = game.perform_action(ActionInput(id=0))

    if ACTIONS_LOG_PATH.is_file():
        for line in ACTIONS_LOG_PATH.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            action = json.loads(line)
            frame = game.perform_action(ActionInput(**action))

    reward = 1.0 if frame.state.value == "WIN" else 0.0

    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(str(reward))

    print(f"Final state: {frame.state.value}")
    print(f"Reward: {reward}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
