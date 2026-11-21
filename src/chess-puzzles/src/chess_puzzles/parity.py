"""Prepare, execute and summarize matched original/Harbor experiments.

Generation and model-list lookup do not run paid inference. Runs require explicit
--execute and complete budgets; mock tests are recorded separately from model parity.
"""

import argparse
import getpass
import hashlib
import importlib.metadata
import json
import math
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .adapter import PARITY_IDS, ChessPuzzlesAdapter, UPSTREAM_COMMIT
from .source import prepare_source
from .runtime import HTTP_MAX_RETRIES
from .token_counting import count_settings, validate_count_mode

HARBOR_TIMEOUT_GRACE_SEC = 300


def validate_settings(settings, *, for_run=False):
    mode = settings.get("token_count_mode", "provider")
    validate_count_mode(mode)
    if mode == "local" and not settings.get("model", "").startswith("anthropic/"):
        raise ValueError("Local counting is validated only for Anthropic models")
    if settings.get("sample_ids") != list(PARITY_IDS):
        raise ValueError("Use the ten predeclared puzzle IDs in their original order")
    if settings.get("sanity_ids") != list(PARITY_IDS[:5]):
        raise ValueError("Sanity uses the first five predeclared puzzle IDs")
    if settings.get("runs_per_side") != 3:
        raise ValueError("The agreed plan has three formal runs per side")
    if for_run:
        for field in ("max_output_tokens", "response_max_tokens", "compaction_threshold_tokens", "attempt_timeout_sec"):
            value = settings.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"Set an explicit positive {field} before paid runs")
        if settings.get("reasoning_effort") not in (None, "low", "medium", "high", "xhigh", "max"):
            raise ValueError("Unsupported reasoning effort")
        if settings["model"] == "anthropic/claude-haiku-5-5" and settings.get("reasoning_effort") is not None:
            raise ValueError("Pinned Inspect drops forced tool_choice with explicit reasoning_effort; use model default (null) until a symmetric provider fix is verified")
    if "api_key" in settings or "ANTHROPIC_API_KEY" in settings:
        raise ValueError("Keep credentials out of experiment settings")


def model_list(base_url, wanted):
    if base_url.rstrip("/") != "https://app.ppapi.ai":
        raise ValueError("This helper is restricted to the documented parity service")
    key = os.environ.get("ANTHROPIC_API_KEY") or getpass.getpass("Parity API key (hidden): ")
    if not key.strip():
        raise ValueError("API key is empty")

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = Request(base_url.rstrip("/") + "/v1/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            body = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Model-list request returned HTTP {error.code}; no inference was run") from None
    models = sorted(item["id"] for item in body.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str))
    for name in models:
        if "haiku" in name.lower():
            print(name)
    exact = wanted.removeprefix("anthropic/")
    print(f"Requested model listed: {exact in models}. Model listing alone does not verify tool/thinking support.")


def prepare(output_dir, settings):
    validate_settings(settings)
    source = prepare_source(settings.get("source_dir"))
    return ChessPuzzlesAdapter(
        output_dir, data_path=source / "bench/task/chess_puzzles/puzzles.csv",
        variant="original", split="parity",
    ).run()


def harbor_config(settings, dataset, ids, jobs_dir, name):
    return {
        "job_name": name, "jobs_dir": str(jobs_dir.resolve()), "n_attempts": 1,
        "n_concurrent_trials": 1, "quiet": True, "retry": {"max_retries": 0},
        "environment": {"type": "docker", "delete": True},
        "datasets": [{"path": str(dataset.resolve()),
                      "task_names": [f"*chess-puzzles-{i:03d}" for i in ids]}],
        "agents": [{"import_path": "chess_puzzles.agent:EpochChessAgent",
                    "model_name": settings["model"],
                    # Inspect owns the matched deadline; Harbor allows worker startup/cleanup.
                    "override_timeout_sec": settings["attempt_timeout_sec"] + HARBOR_TIMEOUT_GRACE_SEC,
                    "kwargs": {"max_output_tokens": settings["max_output_tokens"],
                               "response_max_tokens": settings["response_max_tokens"],
                               "token_count_mode": settings.get("token_count_mode", "provider"),
                               "compaction_threshold_tokens": settings["compaction_threshold_tokens"],
                               "reasoning_effort": settings.get("reasoning_effort"),
                               "source_dir": str(prepare_source(settings.get("source_dir"))),
                               "inspect_base_url": settings.get("base_url"),
                               "attempt_timeout_sec": settings["attempt_timeout_sec"],
                               "mock_scenario": settings.get("mock_scenario")}}],
    }


def collect_harbor(job, ids, simulated=False):
    rows = []
    for file in sorted(job.glob("*/result.json")):
        trial = json.loads(file.read_text())
        match = re.search(r"chess-puzzles-(\d+)", trial["task_name"])
        if not match:
            raise RuntimeError(f"Unknown task name in {file}")
        diagnosis = file.parent / "agent/inspect/outcome.json"
        outcome = json.loads(diagnosis.read_text()) if diagnosis.exists() else {}
        samples = outcome.get("samples", [])
        sample = samples[0] if len(samples) == 1 else {}
        reward = ((trial.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        failed = bool(trial.get("exception_info")) or outcome.get("status") == "incomplete" or reward not in (0, 1)
        rows.append({"id": int(match.group(1)), "reward": None if failed else reward,
                     "status": ("limited" if sample.get("limit") else "error") if failed else "complete",
                     "limit": sample.get("limit"), "exception": trial.get("exception_info"),
                     "answer": sample.get("answer"), "metadata": sample.get("metadata"),
                     "usage": outcome.get("usage"), "result": str(file),
                     "token_counting": outcome.get("token_counting"),
                     "compactions": sample.get("compactions", [])})
    ids_match = sorted(row["id"] for row in rows) == sorted(ids)
    complete = ids_match and all(row["status"] == "complete" for row in rows)
    result = {"side": "harbor", "simulated": simulated, "samples": rows,
              "status": "complete" if complete else "incomplete",
              "accuracy": statistics.mean(row["reward"] for row in rows) if complete else None}
    job.mkdir(parents=True, exist_ok=True)
    (job / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    if not ids_match:
        raise RuntimeError("Harbor has missing, duplicate or unexpected trials; see summary.json")
    if not complete:
        raise RuntimeError("Harbor trial failed or was limited; see summary.json and native logs")
    return result


def require_key():
    # Get credentials before creating directories: empty input/Ctrl-C leaves no attempt.
    key = os.environ.get("ANTHROPIC_API_KEY") or getpass.getpass("Parity API key (hidden): ")
    if not key.strip():
        raise ValueError("API key is empty")
    return key.strip()


def check_retry(run_dir, retry_failed, retry_reason):
    if not run_dir.exists():
        if retry_failed:
            raise ValueError("There is no failed round to retry")
        return
    if (run_dir / "pair-complete.json").exists():
        raise ValueError("Completed rounds cannot be replaced")
    if not retry_failed or not retry_reason or not retry_reason.strip():
        raise ValueError("Existing attempt: inspect its logs; retry requires --retry-failed --retry-reason")
    if not (run_dir / "failure.json").is_file():
        raise ValueError("No failure record; the round may still be running. Inspect it before recovery")


def start_round(root, run_dir, retry_failed, retry_reason):
    check_retry(run_dir, retry_failed, retry_reason)
    if run_dir.exists():
        archive = root / "failed-attempts"
        archive.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archived = archive / f"{run_dir.name}-{stamp}"
        run_dir.rename(archived)
        run_dir.mkdir()
        (run_dir / "retry.json").write_text(json.dumps({
            "previous_attempt": str(archived), "reason": retry_reason,
            "policy": "Repeat both sides of this incomplete round; retain all earlier attempts."
        }, indent=2) + "\n")
    else:
        run_dir.mkdir()


def verify_dataset(dataset):
    manifest = json.loads((dataset / "generation_manifest.json").read_text())
    expected = [f"chess-puzzles-{i:03d}" for i in PARITY_IDS]
    if (manifest.get("variant") != "original" or manifest.get("split") != "parity"
            or manifest.get("task_ids") != expected or manifest.get("upstream_commit") != UPSTREAM_COMMIT):
        raise ValueError("Prepared dataset is not the original-prompt parity subset; use a fresh --output-dir")
    if (manifest.get("verifier_mode") != "separate"
            or manifest.get("submission_artifacts") != ["/app/answer.txt"]):
        raise ValueError("Prepared dataset predates the separate verifier; regenerate into a fresh --output-dir")
    import tomllib
    actual = sorted(p.parent.name for p in dataset.glob("*/task.toml"))
    if actual != expected:
        raise ValueError("Prepared dataset has missing or extra tasks")
    for name in expected:
        config = tomllib.loads((dataset / name / "task.toml").read_text())
        if config["task"]["name"] != f"epoch-ai/chess-puzzles-original__{name}":
            raise ValueError("Prepared task uses an older variant name; regenerate into a fresh --output-dir")
        verifier = config.get("verifier", {})
        if (verifier.get("environment_mode") != "separate"
                or verifier.get("environment", {}).get("network_mode") not in (None, "public")
                or verifier.get("environment", {}).get("docker_image")
                or config.get("artifacts") != ["/app/answer.txt"]
                or not (dataset / name / "tests/Dockerfile").is_file()):
            raise ValueError("Prepared task lacks the separate answer-file verifier; regenerate into a fresh --output-dir")


def run_pair(settings, root, phase, round_number, execute, *, dataset=None,
             retry_failed=False, retry_reason=None):
    validate_settings(settings, for_run=True)
    if phase == "sanity" and round_number != 1:
        raise ValueError("Sanity has one run per side")
    ids = settings["sanity_ids"] if phase == "sanity" else settings["sample_ids"]
    if not execute:
        print(f"Plan only: {phase}, round {round_number}; {len(ids)} tasks per side. Add --execute to run.")
        return
    if settings["model"].startswith("mockllm/"):
        raise ValueError("Use the separate offline test harness for simulations")
    if phase == "formal":
        previous = root / ("sanity-1" if round_number == 1 else f"formal-{round_number-1}")
        if not (previous / "pair-complete.json").exists():
            raise ValueError("Complete both sides of the preceding phase/round first")
    run_dir = root / f"{phase}-{round_number}"
    check_retry(run_dir, retry_failed, retry_reason)
    key = require_key()
    source = prepare_source(settings.get("source_dir"))
    dataset = Path(dataset) if dataset is not None else root / "tasks"
    if not dataset.exists():
        prepare(dataset, settings)
    verify_dataset(dataset)
    task_hashes = {str(p.relative_to(dataset)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(dataset.rglob('*')) if p.is_file()}
    package = Path(__file__).parent
    files = sorted(p for p in package.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    code_hashes = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions = {name: importlib.metadata.version(name) for name in ('harbor', 'inspect-ai', 'anthropic', 'chess', 'tiktoken')}
    settings = {**settings, "source_dir": str(source), "upstream_commit": UPSTREAM_COMMIT,
                "token_count_mode": settings.get("token_count_mode", "provider"),
                "token_counting": count_settings(settings.get("token_count_mode", "provider")),
                "adapter_files_sha256": code_hashes, "package_versions": versions,
                "task_files_sha256": task_hashes, "python_version": sys.version,
                "http_max_retries": HTTP_MAX_RETRIES, "inspect_max_retries": 0,
                "harbor_timeout_grace_sec": HARBOR_TIMEOUT_GRACE_SEC}
    snapshot = json.dumps(settings, sort_keys=True, indent=2) + "\n"
    fingerprint = root / "settings.json"
    if fingerprint.exists() and fingerprint.read_text() != snapshot:
        raise ValueError("Settings changed; use a new experiment directory and retain old evidence")
    root.mkdir(parents=True, exist_ok=True)
    fingerprint.write_text(snapshot)
    start_round(root, run_dir, retry_failed, retry_reason)
    env = {**os.environ, "ANTHROPIC_API_KEY": key}
    stage = "original"
    try:
        command = [sys.executable, "-m", "chess_puzzles.original", "--settings", str(fingerprint.resolve()),
                   "--sample-id", *map(str, ids), "--log-dir", str((run_dir / "original").resolve())]
        subprocess.run(command, check=True, env=env)
        stage = "harbor"
        config = harbor_config(settings, dataset, ids, run_dir, "harbor")
        config_path = run_dir / "harbor-config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        subprocess.run([str(Path(sys.executable).with_name("harbor")), "run", "-c", str(config_path)], check=True, env=env)
        collect_harbor(run_dir / "harbor", ids)
        (run_dir / "pair-complete.json").write_text(json.dumps({"phase": phase, "round": round_number,
            "settings_sha256": hashlib.sha256(snapshot.encode()).hexdigest(), "ids": ids}) + "\n")
    except (Exception, KeyboardInterrupt) as error:
        # No raw exception/request body here: API errors may echo confidential headers.
        (run_dir / "failure.json").write_text(json.dumps({
            "stage": stage, "error_type": type(error).__name__, "ids": ids,
            "policy": "Incomplete round, not a score. Inspect logs before explicitly retrying both sides."
        }, indent=2) + "\n")
        raise


def mean_sem(values):
    if len(values) < 2:
        raise ValueError("SEM needs at least two independent runs")
    return {"mean": statistics.mean(values), "sample_sem": statistics.stdev(values) / math.sqrt(len(values))}


def report(root):
    runs = {side: [] for side in ("original", "harbor")}
    per_puzzle = {i: {side: [] for side in runs} for i in PARITY_IDS}
    disagreements = []
    for number in (1, 2, 3):
        folder = root / f"formal-{number}"
        if not (folder / "pair-complete.json").exists():
            raise ValueError(f"Formal round {number} is not complete on both sides")
        scores = {}
        for side in runs:
            result = json.loads((folder / side / "summary.json").read_text())
            if result.get("simulated"):
                raise ValueError("Simulations are not model parity evidence")
            if result.get("status") != "complete":
                raise ValueError("Incomplete evaluations cannot enter the parity report")
            if sorted(row["id"] for row in result["samples"]) != list(PARITY_IDS):
                raise ValueError("Report requires exactly the predeclared ten puzzles")
            scores[side] = {row["id"]: row["reward"] for row in result["samples"]}
            if any(score not in (0, 1) for score in scores[side].values()):
                raise ValueError("Invalid puzzle score")
            accuracy = statistics.mean(scores[side].values())
            if not math.isclose(accuracy, result["accuracy"]):
                raise ValueError("Accuracy disagrees with per-puzzle scores")
            runs[side].append(accuracy)
            for i, score in scores[side].items():
                per_puzzle[i][side].append(score)
        disagreements.append({"round": number,
            "original_only_correct": [i for i in PARITY_IDS if scores["original"][i] > scores["harbor"][i]],
            "harbor_only_correct": [i for i in PARITY_IDS if scores["harbor"][i] > scores["original"][i]]})
    summary = {side: {"runs": values, **mean_sem(values)} for side, values in runs.items()}
    a, b = runs.values()
    summary.update(run_ranges_overlap=max(a) >= min(b) and max(b) >= min(a),
                   all_zero=not any(a + b), per_puzzle=per_puzzle, disagreements=disagreements,
                   metric="accuracy (0–1); sample SEM across three run accuracies, not MSE",
                   interpretation="Descriptive results, not an automatic parity pass. Inspect disagreements; overlap or all-zero scores alone are insufficient.")
    (root / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("models", "probe", "prepare", "run-pair", "report"))
    parser.add_argument("--settings", type=Path, default=Path("parity_settings.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/chess-puzzles-parity-separate"))
    parser.add_argument("--experiment-dir", type=Path, default=Path("jobs/chess-puzzles-separate-parity"))
    parser.add_argument("--phase", choices=("sanity", "formal"), default="sanity")
    parser.add_argument("--round", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Explicitly archive and repeat an incomplete pair, never a completed pair")
    parser.add_argument("--retry-reason", help="Document the diagnosed infrastructure failure")
    args = parser.parse_args()
    try:
        if args.action == "report":
            report(args.experiment_dir)
            return
        settings = json.loads(args.settings.read_text())
        validate_settings(settings)
        if args.action == "models":
            model_list(settings["base_url"], settings["model"])
        elif args.action == "probe":
            from .api_probe import run_probe
            run_probe(settings, args.experiment_dir, args.execute, require_key)
        elif args.action == "prepare":
            print(f"Generated {len(prepare(args.output_dir, settings))} original-prompt tasks")
        else:
            run_pair(settings, args.experiment_dir, args.phase, args.round, args.execute,
                     dataset=args.output_dir, retry_failed=args.retry_failed, retry_reason=args.retry_reason)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
