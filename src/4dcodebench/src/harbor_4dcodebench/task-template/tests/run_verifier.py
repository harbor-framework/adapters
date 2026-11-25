"""Score the delivered world with the original 4DCodeBench scorer and write Harbor rewards.

Runs in the separate verifier container built from `tests/Dockerfile`: the upstream
scorer image with its checkpoints at `/checkpoints`, and this case's reference data
under `/bench` in the scorer's own layout (`scorer/paths.py`):

    /bench/cases/<kind>/<case>/reference.mp4
    /bench/data/<kind>/<case>/world/        synthetic cases
    /bench/data/<kind>/<case>/annotation/   real cases
    /bench/data/<kind>/<case>/estimates/

Harbor re-creates the agent's `/workspace/world` and `/workspace/solution` here. They
are scored as one manifest entry, the same entry `harness/runtime/score.py` writes for
a delivered run (`world` is `<run>/workspace/world`, and the world gate looks for
`solution/build.sh` beside it), with the `runs` root set to `/` so that the entry's
paths are these container paths. The scorer writes `results/reward.json`, `reward.detail.json` and its
arrays to `/logs/verifier/4dcodebench/`, which Harbor keeps with the trial.

Exit status: 0 once `/logs/verifier/reward.json` is written. On a missing input or a
scorer run that produced no complete `reward.json`, no reward file is written and the
exit status is 1, so Harbor reports a verifier failure instead of a low score.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rewards import ScoreConversionError, convert  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
CASE_FILE = TESTS_DIR / "case.json"
BENCH = Path("/bench")
CHECKPOINTS = Path("/checkpoints")
RUNS_ROOT = Path("/")               # the scorer's `--runs` root: entries name container paths
WORKSPACE = Path("/workspace")      # where Harbor re-creates world/ and solution/
LOGS = Path("/logs/verifier")
OUT = LOGS / "4dcodebench"          # the scorer's `out` directory for this world
MANIFEST = Path("/tmp/4dcodebench/manifest.json")


def runs_path(path: Path) -> str:
    """`path` as a manifest path under the `runs` root (`scorer/paths.py`)."""
    return "runs/" + path.relative_to(RUNS_ROOT).as_posix()


def fail(message: str) -> int:
    print(f"4dcodebench verifier: {message}", file=sys.stderr, flush=True)
    (LOGS / "4dcodebench_failure.txt").write_text(message + "\n", encoding="utf-8")
    return 1


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    info = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    case = info["case"]
    video = BENCH / "cases" / case / "reference.mp4"
    if not video.is_file():
        return fail(f"reference video missing from the verifier image: {video}")
    if not CHECKPOINTS.is_dir() or not any(CHECKPOINTS.iterdir()):
        return fail(f"scorer checkpoints missing from the verifier image: {CHECKPOINTS}")
    missing = [name for name in info["required_data"] if not (BENCH / "data" / case / name).exists()]
    if missing:
        return fail(f"reference data missing from the verifier image: {missing}")

    shutil.rmtree(OUT, ignore_errors=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps([{
        "case": case,
        "world": runs_path(WORKSPACE / "world"),
        "out": runs_path(OUT),
    }], indent=2) + "\n", encoding="utf-8")

    command = [
        sys.executable, "-m", "scorer",
        "--manifest", str(MANIFEST),
        "--cases", str(BENCH / "cases"),
        "--data", str(BENCH / "data"),
        "--runs", str(RUNS_ROOT),
        "--checkpoints", str(CHECKPOINTS),
        "--task-timeout", str(info["task_timeout_sec"]),
        "--prepare-timeout", str(info["task_prepare_timeout_sec"]),
    ]
    print("$", " ".join(command), flush=True)
    # The scorer exits nonzero whenever a world had a failure, a closed gate included,
    # so its readings, not its exit status, decide what is written.
    exit_code = subprocess.run(command, cwd=os.environ.get("SCORER_ROOT", "/opt/4dcb")).returncode
    print(f"scorer exit status {exit_code}", flush=True)

    results = OUT / "results"
    reward_path, detail_path = results / "reward.json", results / "reward.detail.json"
    if not reward_path.is_file() or not detail_path.is_file():
        return fail(f"the scorer wrote no {reward_path.name} / {detail_path.name} (exit status {exit_code})")
    try:
        rewards, record = convert(json.loads(reward_path.read_text(encoding="utf-8")),
                                  json.loads(detail_path.read_text(encoding="utf-8")))
    except (ScoreConversionError, json.JSONDecodeError) as error:
        return fail(f"unusable scorer output (exit status {exit_code}): {error}")

    record |= {"case": case, "scorer_exit_status": exit_code,
               "upstream_commit": info["upstream_commit"]}
    (LOGS / "4dcodebench_readings.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (LOGS / "reward.json").write_text(json.dumps(rewards, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")
    print(json.dumps(rewards, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
