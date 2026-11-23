# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Harbor uv_script metric: upstream mean over scorable definitions only.

Each task emits one selected solution's avg_speedup. Do not turn missing scores
into zeros or hide their count. An incomplete cohort still requires diagnosis;
its partial mean is not evidence that the planned parity run completed.
"""

import argparse
import json
import math
from pathlib import Path


def aggregate(rewards):
    scores = []
    unscored = 0
    for reward in rewards:
        if reward is None or reward == {}:
            unscored += 1
            continue
        value = reward["reward"]
        if not math.isfinite(value):
            raise ValueError("Expected a finite upstream speedup")
        scores.append(value)
    result = {}
    if scores:
        result["avg_speedup"] = sum(scores) / len(scores)
    result.update(scored_definitions=len(scores), unscored_definitions=unscored)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    rewards = [
        json.loads(line) for line in args.input.read_text().splitlines() if line.strip()
    ]
    args.output.write_text(json.dumps(aggregate(rewards), allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
