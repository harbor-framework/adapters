"""Run the upstream evaluator and scorer, retaining its full trace output."""

import argparse
import json
import math
from collections import Counter
from contextlib import closing
from pathlib import Path

from assets import check_gpu, prepare


def score_result(result, candidate, baseline, expected):
    """Reject incomplete infrastructure runs before delegating all scoring upstream."""
    traces = result.traces[candidate.definition]
    for solution in (baseline, candidate):
        actual = [t for t in traces if t.solution == solution.name]
        if Counter(t.workload.uuid for t in actual) != Counter(expected):
            raise RuntimeError(
                f"Incomplete evaluation for {solution.name}; no score published"
            )
        if any(t.evaluation is None for t in actual):
            raise RuntimeError("Missing evaluation; no score published")
    # Baseline failures are handled by the upstream scorer: only workloads with
    # a passing baseline participate. Do not add an adapter-only all-pass gate.
    score = result.get_solution_score(candidate.name, baseline_author="baseline")
    if score is None or not math.isfinite(score.avg_speedup):
        raise RuntimeError("No finite comparable upstream score")
    return score


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", type=Path, default=Path("/tests"))
    p.add_argument("--solution", type=Path, default=Path("/workspace/solution.json"))
    p.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for filename in (
        "reward.txt",
        "reward.json",
        "score.json",
        "traces.jsonl",
        "eval_config.json",
    ):
        (args.output / filename).unlink(missing_ok=True)
    from flashinfer_bench import Benchmark, BenchmarkConfig, Solution, TraceSet

    manifest = json.loads((args.task / "manifest.json").read_text())
    baseline = Solution.model_validate_json((args.task / "baseline.json").read_text())
    candidate = Solution.model_validate_json(args.solution.read_text())
    if candidate.definition != manifest["definition"]:
        raise ValueError(f"Solution must target definition {manifest['definition']!r}")
    if candidate.author == "baseline" or candidate.name == baseline.name:
        raise ValueError("Solution must not impersonate the baseline")
    check_gpu(manifest["target_gpu"])
    root = args.task / "data"
    prepare(root, manifest, Path("/tmp/flashinfer-tensors"))
    data = TraceSet.from_path(str(root))
    # Never reuse agent feedback traces or agent-provided baselines.
    fresh = TraceSet(
        root=root,
        definitions=data.definitions,
        workloads=data.workloads,
        solutions={candidate.definition: [baseline, candidate]},
        traces={},
    )
    config = BenchmarkConfig.default()
    (args.output / "eval_config.json").write_text(config.model_dump_json(indent=2))
    with closing(Benchmark(fresh, config)) as bench:
        result = bench.run_all(dump_traces=False)
    with (args.output / "traces.jsonl").open("w") as stream:
        for rows in result.traces.values():
            for trace in rows:
                stream.write(trace.model_dump_json() + "\n")
    score = score_result(result, candidate, baseline, manifest["workload_uuids"])
    (args.output / "score.json").write_text(score.model_dump_json(indent=2))
    # Continuous upstream speedup: deliberately not clamped or converted to pass/fail.
    (args.output / "reward.txt").write_text(str(score.avg_speedup) + "\n")


if __name__ == "__main__":
    main()
