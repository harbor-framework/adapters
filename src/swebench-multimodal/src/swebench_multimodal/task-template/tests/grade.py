import json
import sys
from pathlib import Path

from upstream import (
    EvalType,
    ResolvedStatus,
    TestSpec,
    get_eval_tests_report,
    get_logs_eval,
    get_resolution_status,
)


def grade(tests_dir: Path, log_path: Path) -> dict:
    metadata = json.loads((tests_dir / "task_metadata.json").read_text())
    gold = json.loads((tests_dir / "tests.json").read_text())
    metadata["version"] = str(metadata["version"])
    spec = TestSpec(**metadata)
    status_map, valid = get_logs_eval(spec, str(log_path))
    report = get_eval_tests_report(
        status_map, gold, eval_type=EvalType(spec.eval_type)
    )
    return {
        "instance_id": spec.instance_id,
        "resolved": valid
        and get_resolution_status(report) == ResolvedStatus.FULL.value,
        "valid_test_output": valid,
        "tests_status": report,
    }


if __name__ == "__main__":
    log_dir = Path(sys.argv[1])
    result = grade(Path(__file__).resolve().parent, log_dir / "test_output.log")
    (log_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    (log_dir / "reward.txt").write_text("1\n" if result["resolved"] else "0\n")
