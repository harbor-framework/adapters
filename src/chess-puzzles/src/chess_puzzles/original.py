"""Original evaluation: pinned upstream dataset, prompts, solver and scorer."""

import argparse
import asyncio
import json
from pathlib import Path

from inspect_ai import eval_async

from .runtime import make_model, generation_kwargs
from .source import upstream
from .outcomes import evaluation_outcome, require_complete


async def evaluate(settings, sample_ids, log_dir):
    task = upstream(settings.get("source_dir")).chess_puzzles(
        max_output_tokens=settings["max_output_tokens"],
        compaction_threshold_tokens=settings["compaction_threshold_tokens"],
    )
    kwargs = generation_kwargs(settings["model"], settings.get("reasoning_effort"),
                               settings["response_max_tokens"])
    model = make_model(settings["model"], settings.get("base_url"),
                       mock_scenario=settings.get("mock_scenario"),
                       token_count_mode=settings.get("token_count_mode", "provider"),
                       count_audit_path=Path(log_dir) / "token-counts.jsonl")
    logs = await eval_async(
        task, model=model, sample_id=sample_ids, log_dir=str(log_dir), max_samples=1,
        fail_on_error=True, retry_on_error=0, max_retries=0,
        time_limit=settings["attempt_timeout_sec"], **kwargs,
    )
    if len(logs) != 1:
        raise RuntimeError("Original evaluation returned no unique log")
    log = logs[0]
    result = evaluation_outcome(log, sample_ids, log_dir,
                                settings.get("token_count_mode", "provider"))
    result.update(side="original", simulated=settings["model"].startswith("mockllm/"), accuracy=None)
    if result["status"] != "complete":
        Path(log_dir, "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    require_complete(result)
    rows = result["samples"]
    for sample, row in zip(log.samples, rows, strict=True):
        score = (sample.scores or {}).get("exact")
        if score is None or score.value not in ("C", "I", 0, 1):
            raise RuntimeError(f"Unexpected upstream score for sample {sample.id}")
        row["reward"] = int(score.value in ("C", 1))
    result["accuracy"] = sum(row["reward"] for row in rows) / len(rows)
    Path(log_dir, "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--sample-id", type=int, nargs="+", required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text())
    print(json.dumps(asyncio.run(evaluate(settings, args.sample_id, args.log_dir)), indent=2))


if __name__ == "__main__":
    main()
