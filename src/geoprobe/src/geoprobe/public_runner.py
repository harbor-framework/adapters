"""Run the original W1 loop on public inputs; defer private grading to Harbor.

The only upstream hook replaces post-submission score_case. It is never called
before the model's last action and never supplies feedback to the model.
"""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys


def deferred_score(prediction, case):
    return {"submission_valid": True, "passed": None, "score_kind": "deferred_to_harbor_verifier"}


def submission_from_report(report: dict):
    """Keep genuine agent failures in coverage, and surface infrastructure errors."""
    native = report.get("native_result") or {}
    if report.get("ok") and "prediction" in native:
        return native["prediction"]
    loop = (report.get("event_log_paths") or {}).get("episode_loop") or {}
    turns = loop.get("turns") or []
    last = turns[-1] if turns else {}
    if report.get("outcome") == "budget_exhausted":
        return None
    if report.get("outcome") in {"timeout", "agent_failure"} and last.get("stage") == "execution":
        return None
    raise RuntimeError("Native infrastructure/model-transport failure; inspect runtime-report.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arena-root", type=Path, default=Path("/opt/arena"))
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/agent/native"))
    parser.add_argument("--executor", choices=["openai-compatible", "codex-exec", "probe"], default="openai-compatible")
    parser.add_argument("--model")
    parser.add_argument("--solution", type=Path, help="Probe-only replay for transport checks; not model parity")
    args = parser.parse_args()
    if args.executor != "probe" and not args.model:
        parser.error("--model is required")
    if args.solution and args.executor != "probe":
        parser.error("--solution is only allowed with probe")
    root, workspace = args.arena_root.resolve(), args.workspace.resolve()
    os.environ["EMBODIED_ARENA_ROOT"] = str(root)
    sys.path[:0] = [str(root / "src"), str(root / "runtimes/pukun/scripts")]
    import embodied_harness.w1_runtime as runtime
    runtime.score_case = deferred_score
    public = json.loads((workspace / "public-task.json").read_text())
    if "gt" in public or "provenance" in public:
        raise ValueError("Private annotations must not enter the public runtime")
    args.logs.mkdir(parents=True, exist_ok=True)
    report = args.logs / "runtime-report.json"
    answer = workspace / "answer.json"
    answer.unlink(missing_ok=True)
    sys.argv = [str(root / "scripts/run_w1_native_case.py"),
                "--benchmark", public["benchmark"], "--sample-id", public["sample_id"],
                "--data-root", str(workspace / "data"), "--output", str(report),
                "--agent-trace-root", str(args.logs / "episode"), "--executor", args.executor,
                "--max-agent-iterations", "12", "--max-total-tokens", "120000",
                "--max-agent-attempts", "1", "--llm-num-retries", "0"]
    if args.model:
        sys.argv += ["--model", args.model]
    if args.solution:
        sys.argv += ["--solution", str(args.solution.resolve())]
    try:
        runpy.run_path(str(root / "scripts/run_w1_native_case.py"), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0) and not report.is_file():
            raise RuntimeError(f"Native W1 runtime failed before reporting; inspect {args.logs}") from exc
    result = json.loads(report.read_text())
    submitted = submission_from_report(result)
    # Preserve invalid numeric predictions too: the unchanged private scorer
    # rejects NaN/Infinity as a submission error, rather than an agent crash.
    answer.write_text(json.dumps(submitted, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
