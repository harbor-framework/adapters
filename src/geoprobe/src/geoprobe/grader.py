"""Private verifier entry point using unchanged upstream parsing and scoring."""
import argparse
import json
from pathlib import Path

from geoprobe.rewards import encode_metrics
from geoprobe.upstream.w1_scoring import parse_submission, score_case


def grade(case: dict, answer_path: Path) -> tuple[dict, dict]:
    try:
        if answer_path.stat().st_size > 1_000_000:
            raise ValueError("Answer exceeds 1 MB")
        submitted = json.loads(answer_path.read_text())
    except (OSError, ValueError, UnicodeError) as exc:
        metrics = {"benchmark": case["benchmark"], "sample_id": case["sample_id"], "submission_valid": False,
                   "passed": False, "invalid_reason": "unreadable_answer", "invalid_detail": str(exc)}
    else:
        metrics = score_case(parse_submission(submitted), case)
    return metrics, encode_metrics(case, metrics)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, default=Path("/tests/case.json"))
    parser.add_argument("--answer", type=Path, default=Path("/workspace/answer.json"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    case = json.loads(args.case.read_text())
    metrics, rewards = grade(case, args.answer)
    args.logs.mkdir(parents=True, exist_ok=True)
    (args.logs / "native-metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    (args.logs / "reward.json").write_text(json.dumps(rewards, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
