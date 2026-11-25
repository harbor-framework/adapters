# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Harbor dataset metric for 4DCodeBench: the mean of each reward key over the trials that report it.

Harbor's default `mean` counts a key a trial does not report as 0. A 4DCodeBench
reward file leaves out the metrics that are not scored on its case (reference-world
metrics on real cases; Flow, Track2D, Depth and Uni3D MoGe on synthetic ones;
`excluded` and `uncomputable` readings; geometry quality behind a closed gate), so
those keys are averaged here over the trials that report them, as the original
aggregates them (docs/spec.md, "Executability and scoring").

    uv run metric.py -i rewards.jsonl -o metric.json

Each output key is a reward key's mean; `<key>__n` is the number of trials behind it.
`n_trials` counts every trial, and `n_trials_without_reward` those Harbor recorded no
reward for (a verifier failure), which enter no mean.

The original averages per case first, then over cases; this equals that whenever
every case contributes the same number of trials to a key, e.g. one trial per case.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def aggregate(rewards: list[dict | None]) -> dict[str, float | int]:
    values: dict[str, list[float]] = {}
    for reward in rewards:
        for key, value in (reward or {}).items():
            values.setdefault(key, []).append(float(value))
    result: dict[str, float | int] = {
        "n_trials": len(rewards),
        "n_trials_without_reward": sum(reward is None for reward in rewards),
    }
    for key in sorted(values):
        result[key] = sum(values[key]) / len(values[key])
        result[f"{key}__n"] = len(values[key])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-i", "--input", type=Path, required=True, help="rewards.jsonl, one reward dict or null per line")
    parser.add_argument("-o", "--output", type=Path, required=True, help="where to write the metric JSON")
    args = parser.parse_args()
    lines = [line for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.output.write_text(json.dumps(aggregate([json.loads(line) for line in lines]), indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
