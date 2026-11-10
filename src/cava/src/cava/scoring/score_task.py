"""Verifier entry point: score /app/answer.txt (+ /app/function_calls.jsonl) for one record."""

import json
from pathlib import Path

from cava_score import score_record

ANSWER = Path("/app/answer.txt")
CALLS = Path("/app/function_calls.jsonl")
LOG_DIR = Path("/logs/verifier")


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path("/tests/record.json").read_text())
    subtask, record = spec["subtask"], spec["record"]
    details = {"subtask": subtask}
    try:
        response = ANSWER.read_text(encoding="utf-8") if ANSWER.is_file() else ""
        calls = None
        if subtask == "function_calling":
            calls = []
            if CALLS.is_file():
                for line in CALLS.read_text().splitlines():
                    if line.strip():
                        calls.append(json.loads(line))
            details["function_calls"] = calls
        details["response"] = response
        correct, total = score_record(subtask, record, response, calls)
        reward = correct / total if total else 0.0
    except Exception as exc:  # never award credit on grader failure
        details["error"] = repr(exc)
        reward = 0.0
    details["reward"] = reward
    (LOG_DIR / "grading_details.json").write_text(json.dumps(details, indent=2))
    (LOG_DIR / "reward.txt").write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
