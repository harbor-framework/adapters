"""Decide whether a submission resolves the task.

Two subcommands:

  grade.py list-test-files <test.patch>
      Print the repository paths the test patch touches, one per line.

  grade.py grade <expected.json> <print.log> <log_parser.py> <log dir>
      Run the task's log parser on the printed test output, compare the test
      statuses with the expected FAIL_TO_PASS and PASS_TO_PASS lists, and
      write the reward.

``run_parser`` and ``status_to_report`` follow the original evaluator
(evaluation/evaluate_docker.py) line for line.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


def test_patch_files(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git "):
            continue
        # "diff --git a/<old> b/<new>"; both sides matter for renames.
        rest = line[len("diff --git ") :]
        if " b/" not in rest or not rest.startswith("a/"):
            continue
        old, new = rest[2:].split(" b/", 1)
        for path in (old, new):
            if path and path not in files:
                files.append(path)
    return files


def run_parser(parser_source: str, log: str) -> tuple[dict[str, str], dict[str, Any]]:
    namespace: dict[str, Any] = {}
    started = time.monotonic()
    try:
        exec(compile(parser_source, "<log-parser>", "exec"), namespace)
        parser = namespace.get("parser")
        if not callable(parser):
            raise TypeError("log_parser did not define callable parser(log)")
        raw = parser(log)
        if not isinstance(raw, dict):
            raise TypeError(f"parser returned {type(raw).__name__}, expected dict")
        status: dict[str, str] = {}
        for key, value in raw.items():
            normalized = str(value).lower()
            if normalized not in {"pass", "fail", "skip"}:
                raise ValueError(f"invalid parser status for {key!r}: {value!r}")
            status[str(key)] = normalized
        return status, {
            "ok": True,
            "error": None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "status_count": len(status),
        }
    except Exception as exc:
        return {}, {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "status_count": 0,
        }


def status_to_report(instance: dict[str, Any], status: dict[str, str]) -> dict[str, Any]:
    passed = {key for key, value in status.items() if value == "pass"}
    failed = {key for key, value in status.items() if value == "fail"}
    skipped = {key for key, value in status.items() if value == "skip"}
    f2p = set(instance["FAIL_TO_PASS"])
    p2p = set(instance["PASS_TO_PASS"])
    report = {
        "instance_id": instance["instance_id"],
        "resolved": False,
        "PASS_TO_PASS": {
            "success": sorted(passed & p2p),
            "failure": sorted(failed & p2p),
            "skipped": sorted(skipped & p2p),
            "missing": sorted(p2p - status.keys()),
        },
        "FAIL_TO_PASS": {
            "success": sorted(passed & f2p),
            "failure": sorted(failed & f2p),
            "skipped": sorted(skipped & f2p),
            "missing": sorted(f2p - status.keys()),
        },
    }
    if (
        not report["PASS_TO_PASS"]["failure"]
        and not report["FAIL_TO_PASS"]["failure"]
        and len(report["FAIL_TO_PASS"]["success"]) > 0
    ):
        report["resolved"] = True
    return report


def grade(expected_path: Path, log_path: Path, parser_path: Path, out_dir: Path) -> int:
    instance = json.loads(expected_path.read_text(encoding="utf-8"))
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    status, parser = run_parser(parser_path.read_text(encoding="utf-8"), log)
    report = status_to_report(instance, status)
    summary = {
        "instance_id": report["instance_id"],
        "resolved": bool(parser["ok"] and report["resolved"]),
        "parser": parser,
        "counts": {
            group: {key: len(value) for key, value in report[group].items()}
            for group in ("FAIL_TO_PASS", "PASS_TO_PASS")
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out_dir / "reward.txt").write_text("1\n" if summary["resolved"] else "0\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "list-test-files":
        for path in test_patch_files(Path(argv[2]).read_text(encoding="utf-8", errors="replace")):
            print(path)
        return 0
    if len(argv) == 6 and argv[1] == "grade":
        return grade(Path(argv[2]), Path(argv[3]), Path(argv[4]), Path(argv[5]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
