"""Write src/cava/data/parity_ids.json: the parity subset (proposal, pending sign-off).

All 151 deception items; a seeded sample of 100 items from each other subtask. Item ids
match prepare_manifests.py.

Usage: python make_parity_ids.py --cava-repo /path/to/CAVA
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

SEED = 20261011
PER_SUBTASK = 100
SIZES = {"jeopardy": 1000, "multimodal_instruction_following": 1000, "jailbreak": 520}
PIPE = "pipeline_gpt-4o_gpt-4o-mini-tts_gpt-4o-mini-transcribe"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cava-repo", type=Path, required=True)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parents[1] / "src/cava/data/parity_ids.json")
    args = ap.parse_args()

    rng = random.Random(SEED)
    n_werewolf = len((args.cava_repo / "data/Werewolf/werewolf.jsonl").read_text().splitlines())
    ids = {"deception_detection": [f"{i:04d}" for i in range(n_werewolf)]}
    for subtask, size in SIZES.items():
        ids[subtask] = [f"{i:04d}" for i in sorted(rng.sample(range(size), PER_SUBTASK))]
    ref = args.cava_repo / f"data/function_calling_test/audio_inputs.jsonl_{PIPE}_function_calling"
    fc = [re.sub(r"[^a-z0-9]+", "-", json.loads(l)["raw_data"]["file_id"].lower()).strip("-")
          for l in ref.read_text().splitlines()]
    ids["function_calling"] = sorted(rng.sample(fc, PER_SUBTASK))
    args.out.write_text(json.dumps(ids, indent=1) + "\n")
    print({k: len(v) for k, v in ids.items()}, "->", args.out)


if __name__ == "__main__":
    main()
