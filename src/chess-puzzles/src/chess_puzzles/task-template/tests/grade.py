"""Score /app/answer.txt against the puzzle's best move (Chess Puzzles 2.0.x exact match).

A wrong or missing answer is a legitimate reward of 0, not a verifier error, so the script
exits 0 whenever it wrote a reward. A crash (bad record, unreadable file) exits non-zero and
leaves no reward file, so it cannot be mistaken for a low score.
"""

import argparse
import json
from pathlib import Path

from scoring import is_correct


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer", type=Path, default=Path("/app/answer.txt"))
    parser.add_argument("--record", type=Path, default=Path("/tests/record.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Remove a stale reward first so a crash below cannot reuse an earlier result.
    (args.output_dir / "reward.txt").unlink(missing_ok=True)

    record = json.loads(args.record.read_text())
    if args.answer.exists():
        answer = args.answer.read_text(encoding="utf-8", errors="replace")
        status = "scored"
        reward = 1 if is_correct(answer, record["target"]) else 0
    else:
        answer = None
        status = "missing_answer"
        reward = 0

    result = {
        "id": record["id"],
        "reward": reward,
        "status": status,
        "answer": answer,
        "target": record["target"],
    }
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output_dir / "reward.txt").write_text(f"{reward}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
