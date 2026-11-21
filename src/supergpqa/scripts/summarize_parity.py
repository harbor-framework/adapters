"""Audit saved paired runs and export the parity report data; no network/model calls."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from supergpqa.direct import EXPECTED_RETURNED_MODEL
from supergpqa.scoring import aggregate, score_response


def statistics_for(values: list[float]) -> dict:
    return {
        "runs": values,
        "mean": statistics.mean(values),
        "sample_sem": statistics.stdev(values) / math.sqrt(len(values)),
        "range": [min(values), max(values)],
    }


def collect(root: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((root / "manifest.json").read_text())
    ids = manifest["task_ids"]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("Expected exactly 100 unique selected UUIDs")
    records = [
        json.loads(
            (root / "tasks" / ("supergpqa-" + uid) / "tests/record.json").read_text()
        )
        for uid in ids
    ]
    by_id = {row["uuid"]: row for row in records}
    requests: dict[str, set[str]] = defaultdict(set)
    metrics: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    run_results = []
    rows = []
    score_maps = {}
    models: Counter = Counter()
    token_usage: Counter = Counter()
    elapsed = []
    timestamps = []
    for index in range(1, 4):
        for side in ("original", "harbor"):
            directory = root / f"run-{index}" / side
            files = list(directory.glob("*/score.json"))
            scores = [json.loads(path.read_text()) for path in files]
            if len(scores) != 100 or {score["uuid"] for score in scores} != set(ids):
                raise ValueError(f"Incomplete/duplicate UUID coverage: {directory}")
            score_maps[index, side] = {
                score["uuid"]: score["reward"] for score in scores
            }
            for uid in ids:
                trial = directory / uid
                agent = trial / "agent"
                score = json.loads((trial / "score.json").read_text())
                call = json.loads((agent / "call.json").read_text())
                request = json.loads((agent / "request.json").read_text())
                response = json.loads((agent / "response.json").read_text())
                text = (agent / "response.txt").read_bytes().decode("utf-8")
                if (
                    call["status"] != "complete"
                    or response["model"] != EXPECTED_RETURNED_MODEL
                ):
                    raise ValueError(f"Unfinished call or changed model: {trial}")
                if response["choices"][0]["message"]["content"] != text:
                    raise ValueError(f"Saved response differs from API JSON: {trial}")
                parsed = score_response(by_id[uid], text)
                if parsed["reward"] != score["reward"]:
                    raise ValueError(f"Scorer replay disagreement: {trial}")
                if side == "harbor":
                    native = json.loads((trial / "result.json").read_text())
                    if (
                        native.get("exception_info")
                        or native["verifier_result"]["rewards"]["reward"]
                        != score["reward"]
                    ):
                        raise ValueError(
                            f"Native Harbor trial failed or reward differs: {trial}"
                        )
                signature = hashlib.sha256(
                    json.dumps(request, sort_keys=True).encode()
                ).hexdigest()
                requests[uid].add(signature)
                models[response["model"]] += 1
                usage = response.get("usage") or {}
                for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    token_usage[field] += usage.get(field, 0)
                token_usage["reasoning_tokens"] += (
                    usage.get("completion_tokens_details") or {}
                ).get("reasoning_tokens", 0)
                elapsed.append(call["elapsed_sec"])
                timestamps.extend([call["started_at"], call["ended_at"]])
                rows.append(
                    {
                        "run": index,
                        "side": side,
                        "uuid": uid,
                        "reward": score["reward"],
                        "gold": by_id[uid]["answer_letter"],
                        "extracted_answer": parsed["extracted_answer"],
                        "parse_status": parsed["status"],
                        "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "request_sha256": signature,
                        "returned_model": response["model"],
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "elapsed_sec": call["elapsed_sec"],
                    }
                )
            result = aggregate(records, scores)
            run_results.append(
                {
                    "run": index,
                    "side": side,
                    "count": 100,
                    "correct": sum(s["reward"] for s in scores),
                    "metrics": result,
                }
            )
            for name in (
                "sample_accuracy",
                "discipline_accuracy",
                "field_accuracy",
                "subfield_accuracy",
            ):
                metrics[name][side].append(result[name])
            for difficulty, value in result["difficulty_accuracy"].items():
                metrics["difficulty_" + difficulty][side].append(value)
    if not all(len(signatures) == 1 for signatures in requests.values()):
        raise ValueError("Effective request differs across sides or repetitions")
    comparisons = {}
    for name, sides in metrics.items():
        original = sides["original"]
        harbor = sides["harbor"]
        comparisons[name] = {
            "original": statistics_for(original),
            "harbor": statistics_for(harbor),
            "ranges_overlap": max(original) >= min(harbor)
            and max(harbor) >= min(original),
        }
    paired = []
    for index in range(1, 4):
        a, b = score_maps[index, "original"], score_maps[index, "harbor"]
        paired.append(
            {
                "run": index,
                "both_correct": sum(a[u] == b[u] == 1 for u in ids),
                "both_incorrect": sum(a[u] == b[u] == 0 for u in ids),
                "original_only_correct": sum(a[u] == 1 and b[u] == 0 for u in ids),
                "harbor_only_correct": sum(a[u] == 0 and b[u] == 1 for u in ids),
            }
        )
    result = {
        "formal_tasks": 600,
        "unique_questions": 100,
        "full_bank_size": 26529,
        "sampling_rate": 100 / 26529,
        "seed": 42,
        "model_versions": dict(models),
        "all_request_configs_identical": True,
        "all_saved_responses_match_api": True,
        "all_saved_scores_replay": True,
        "native_harbor_exceptions_in_selected_results": 0,
        "started_at_utc": datetime.fromtimestamp(min(timestamps), UTC).isoformat(),
        "finished_at_utc": datetime.fromtimestamp(max(timestamps), UTC).isoformat(),
        "formal_token_usage": dict(token_usage),
        "usd_billed_cost": None,
        "api_latency_sec": {
            "mean": statistics.mean(elapsed),
            "median": statistics.median(elapsed),
            "max": max(elapsed),
        },
        "discipline_counts": dict(Counter(r["discipline"] for r in records)),
        "difficulty_counts": dict(Counter(r["difficulty"] for r in records)),
        "metrics": comparisons,
        "run_results": run_results,
        "paired_outcomes": paired,
    }
    return result, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report, rows = collect(args.experiment_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    with (args.output_dir / "task_scores.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                "formal_tasks": report["formal_tasks"],
                "primary_metric": report["metrics"]["sample_accuracy"],
                "formal_token_usage": report["formal_token_usage"],
                "discipline_counts": report["discipline_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
