"""Prepare or run the paired 100-question parity experiment. No implicit API calls."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
from pathlib import Path

from supergpqa.adapter import PACKAGE_DIR, SuperGPQAAdapter, load_records, parity_subset
from supergpqa.direct import (
    DEFAULT_SETTINGS,
    EXPECTED_RETURNED_MODEL,
    VERSION,
    complete,
    digest,
    endpoint_url,
    payload,
    save_json,
)
from supergpqa.parity_upstream import load_upstream, score_original
from supergpqa.scoring import aggregate, score_response


def freeze(path: Path, value: dict) -> None:
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(
                f"Experiment configuration changed: {path}; use a new output directory"
            )
    else:
        save_json(path, value)


def prepare(root: Path, output: Path) -> tuple[list[dict], dict, dict]:
    records = parity_subset(
        load_records(root / "data/SuperGPQA-all.jsonl", output / "cache"), 100, 42
    )
    prompts, parser = load_upstream(root)
    manifest = {
        "seed": 42,
        "task_ids": [r["uuid"] for r in records],
        "sanity_task_ids": [r["uuid"] for r in records[:8]],
        "size": 100,
        "settings": DEFAULT_SETTINGS,
        "expected_returned_model": EXPECTED_RETURNED_MODEL,
        "agent_version": VERSION,
        "source_pins": json.loads(
            (PACKAGE_DIR.parents[1] / "source_pins.json").read_text()
        ),
        "code_hashes": {
            p.name: digest(p.read_text()) for p in PACKAGE_DIR.glob("*.py")
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    freeze(output / "manifest.json", manifest)
    tasks = output / "tasks"
    if not tasks.exists():
        SuperGPQAAdapter(tasks, records).run()
    if {p.name for p in tasks.iterdir() if p.is_dir()} != {
        SuperGPQAAdapter.task_id(r) for r in records
    }:
        raise ValueError("Task directory coverage differs from the selected manifest")
    for row in records:
        instruction = (
            tasks / SuperGPQAAdapter.task_id(row) / "instruction.md"
        ).read_text()
        if instruction != prompts[row["uuid"]]:
            raise ValueError(f"Original/Harbor prompt mismatch: {row['uuid']}")
        for text in (f"Answer: {row['answer_letter']}", "", "Answer: Z"):
            if score_original(row, text, parser) != score_response(row, text)["reward"]:
                raise ValueError("Original/Harbor scorer mismatch")
    save_json(
        output / "preflight.json",
        {
            "questions": len(records),
            "prompt_pairs_identical": 100,
            "independent_scorer_controls": 300,
            "model_calls": 0,
        },
    )
    return records, {r["uuid"]: prompts[r["uuid"]] for r in records}, parser


async def original_one(row: dict, prompt: str, parser: dict, directory: Path) -> dict:
    # Only HTTP runs in a worker: upstream regex uses signal timeouts on the main thread.
    response = await asyncio.to_thread(complete, prompt, directory / "agent")
    reward = score_original(row, response, parser)
    if reward != score_response(row, response)["reward"]:
        raise ValueError("Scorer disagreement on an actual model response")
    result = {"uuid": row["uuid"], "reward": reward}
    save_json(directory / "score.json", result)
    return result


async def harbor_one(
    row: dict, prompt: str, parser: dict, directory: Path, tasks: Path
) -> dict:
    from harbor.models.trial.config import TrialConfig
    from harbor.trial.trial import Trial

    result_path = directory / "result.json"
    if not result_path.exists():
        config = TrialConfig.model_validate(
            {
                "task": {"path": str(tasks / SuperGPQAAdapter.task_id(row))},
                "trial_name": directory.name,
                "trials_dir": str(directory.parent),
                "agent": {
                    "import_path": "supergpqa.harbor_agent:SuperGPQADirectAgent",
                    "model_name": DEFAULT_SETTINGS["model"],
                    "skip_model_parsing": True,
                },
                "environment": {"type": "docker", "force_build": False, "delete": True},
            }
        )
        trial = await Trial.create(config)
        await trial.run()
    raw = json.loads(result_path.read_text())
    if raw.get("exception_info"):
        raise RuntimeError(f"Harbor infrastructure exception for {row['uuid']}")
    reward = (raw.get("verifier_result") or {}).get("rewards", {}).get("reward")
    if reward not in (0, 1):
        raise RuntimeError("Missing/invalid Harbor verifier reward")
    response = (directory / "agent/response.txt").read_bytes().decode("utf-8")
    request = json.loads((directory / "agent/request.json").read_text())
    if request != payload(prompt):
        raise ValueError(
            "Effective Harbor request differs from the original-side request"
        )
    if reward != score_original(row, response, parser):
        raise ValueError(
            "Harbor verifier and upstream parser disagree on the same response"
        )
    result = {"uuid": row["uuid"], "reward": reward}
    save_json(directory / "score.json", result)
    return result


async def run_side(
    side: str,
    rows: list[dict],
    prompts: dict,
    parser: dict,
    directory: Path,
    tasks: Path,
    concurrency: int,
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    failed = asyncio.Event()

    async def one(row):
        async with semaphore:
            if failed.is_set():
                raise RuntimeError("Not started because an earlier task failed")
            trial_dir = directory / row["uuid"]
            try:
                if side == "original":
                    return await original_one(
                        row, prompts[row["uuid"]], parser, trial_dir
                    )
                return await harbor_one(
                    row, prompts[row["uuid"]], parser, trial_dir, tasks
                )
            except Exception as exc:
                failed.set()
                save_json(
                    trial_dir / "infrastructure-error.json",
                    {"uuid": row["uuid"], "type": type(exc).__name__},
                )
                raise

    # Gather all in-flight operations before stopping, so successful calls remain resumable.
    results = await asyncio.gather(*(one(row) for row in rows), return_exceptions=True)
    if any(isinstance(r, BaseException) for r in results):
        raise RuntimeError(
            f"{side} has infrastructure failures; diagnose saved artifacts before resuming"
        )
    scores = [r for r in results if isinstance(r, dict)]
    summary = {
        "side": side,
        "count": len(scores),
        "scores": scores,
        "accuracy": sum(r["reward"] for r in scores) / len(scores),
        "metrics": aggregate(rows, scores),
    }
    save_json(directory / "summary.json", summary)
    print(
        f"{directory.name}/{side}: {len(scores)} tasks, accuracy={summary['accuracy']:.4f}",
        flush=True,
    )
    return summary


def summarize(output: Path) -> dict:
    runs = {
        side: [
            json.loads((output / f"run-{i}" / side / "summary.json").read_text())[
                "accuracy"
            ]
            for i in range(1, 4)
        ]
        for side in ("original", "harbor")
    }
    report = {
        side: {
            "runs": values,
            "mean": statistics.mean(values),
            "sample_sem": statistics.stdev(values) / math.sqrt(len(values)),
            "range": [min(values), max(values)],
        }
        for side, values in runs.items()
    }
    report["ranges_overlap"] = max(runs["original"]) >= min(runs["harbor"]) and max(
        runs["harbor"]
    ) >= min(runs["original"])
    save_json(output / "summary.json", report)
    return report


async def execute(
    rows: list[dict],
    prompts: dict,
    parser: dict,
    output: Path,
    concurrency: int,
    sanity_only: bool,
) -> None:
    base = os.environ.get("SUPERGPQA_BASE_URL", "")
    endpoint_url(base)
    if not os.environ.get("SUPERGPQA_API_KEY"):
        raise ValueError("Set SUPERGPQA_API_KEY in the process environment")
    import importlib.metadata

    freeze(
        output / "runtime.json",
        {
            "base_url": base,
            "python": platform.python_version(),
            "harbor": importlib.metadata.version("harbor"),
            "concurrency": concurrency,
            "timeout_sec": 300,
            "automatic_retries": 0,
            "planned_calls": 616,
            "transport": "python-stdlib-urllib",
            "expected_returned_model": EXPECTED_RETURNED_MODEL,
            "settings": DEFAULT_SETTINGS,
        },
    )
    stages = [("sanity", rows[:8])] + (
        [] if sanity_only else [(f"run-{i}", rows) for i in range(1, 4)]
    )
    for stage, selected in stages:
        for side in ("original", "harbor"):
            await run_side(
                side,
                selected,
                prompts,
                parser,
                output / stage / side,
                output / "tasks",
                concurrency,
            )
    if not sanity_only:
        print(json.dumps(summarize(output), indent=2))


def main() -> None:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--upstream-repo", type=Path, required=True)
    arg.add_argument("--output-dir", type=Path, required=True)
    arg.add_argument(
        "--execute",
        action="store_true",
        help="Perform paid calls; otherwise prepare offline only",
    )
    arg.add_argument("--sanity-only", action="store_true")
    arg.add_argument("--concurrency", type=int, default=4)
    args = arg.parse_args()
    if args.concurrency < 4:
        arg.error("Concurrency below 4 requires the user's approval")
    root, output = args.upstream_repo.resolve(), args.output_dir.resolve()
    rows, prompts, parser = prepare(root, output)
    if args.execute:
        asyncio.run(
            execute(rows, prompts, parser, output, args.concurrency, args.sanity_only)
        )
    else:
        print(f"Offline preflight passed: {len(rows)} matched tasks. No model calls.")


if __name__ == "__main__":
    main()
