"""Aggregate six independently validated environment analyses with equal weights."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from analyze_parity import ValidationError, canonical_hash, read_json, require, score, summary

COUNTS = {"babyai": 50, "babaisai": 120, "textworld": 30, "crafter": 10, "nle": 5, "minihack": 40}
FIXTURES = Path(__file__).resolve().parents[1] / "src/balrog/fixtures"
SDK_PACKAGES = ("openai", "anthropic", "google-genai", "omegaconf", "tqdm")


def frozen_scope(name):
    path = FIXTURES / ("manifest.json" if name == "babyai" else name + "_manifest.json")
    manifest = read_json(path)
    task_ids = [case["episode"]["task_id"] for case in manifest["cases"]]
    require(len(task_ids) == COUNTS[name] and len(task_ids) == len(set(task_ids)), "Invalid packaged frozen scope")
    require(manifest["splits"]["full"] == task_ids, "Packaged full split differs from frozen cases")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "task_ids": task_ids,
            "task_ids_sha256": canonical_hash(task_ids), "source_commits": manifest["source_commits"]}


def sdk_versions(analysis):
    runtimes = analysis["provenance"]["runtime_versions_by_side"]
    by_side = {}
    for side in ("native", "harbor"):
        packages = runtimes[side]["packages"]
        require(all(isinstance(packages.get(name), str) and packages[name] for name in SDK_PACKAGES),
                "Missing model SDK version provenance")
        # Environment libraries and Python can differ across game images. These
        # shared SDKs, which implement model requests, must stay fixed.
        by_side[side] = {name: packages[name] for name in SDK_PACKAGES}
    require(by_side["native"] == by_side["harbor"], "Native and Harbor model SDK versions differ")
    return by_side["native"]


def aggregate(analyses):
    require(len(analyses) == 6, "Exactly six environment analyses are required")
    by_env = {}
    settings = revision = runs = runner = sdk = None
    for analysis in analyses:
        manifest = analysis.get("manifest", {})
        name = manifest.get("env_name")
        require(name in COUNTS and name not in by_env, "Unknown or duplicate environment")
        require(analysis.get("kind") == name + "_parity_analysis" and analysis.get("analysis_only") is True,
                "Use validated environment analysis artifacts")
        expected = frozen_scope(name)
        require(manifest.get("split") in {"full", "parity"}, "Use the complete frozen environment split")
        for key in ("sha256", "task_ids", "task_ids_sha256"):
            require(manifest.get(key) == expected[key], "Frozen environment scope differs: " + name + ": " + key)
        require(analysis["provenance"]["source_commits"] == expected["source_commits"],
                "Environment source revisions differ from frozen manifest")
        current = analysis["provenance"]["settings"]
        # Native game/action budgets differ by environment; model/agent settings
        # must still be identical across the six components of a suite run.
        identity = {key: current[key] for key in ("agent", "client")}
        commit = analysis["provenance"]["source_commits"]["balrog"]
        current_runner = analysis["provenance"].get("runner_sha256")
        require(isinstance(current_runner, str) and re.fullmatch(r"[0-9a-f]{64}", current_runner),
                "Missing runner code checksum")
        current_sdk = sdk_versions(analysis)
        n = analysis["number_of_runs_per_side"]
        require(type(n) is int and n >= 2, "At least two complete suite runs are required")
        if settings is None:
            settings, revision, runs, runner, sdk = identity, commit, n, current_runner, current_sdk
        require((identity, commit, n, current_runner, current_sdk) == (settings, revision, runs, runner, sdk),
                "Model, agent, BALROG revision, runner, SDK versions or run counts differ")
        for side in ("native", "harbor"):
            values = analysis[side]["runs"]
            require(len(values) == n, "Incomplete run array")
            for value in values:
                score(value, name)
            require(summary(values) == analysis[side], "Environment statistics differ from raw run arrays")
        by_env[name] = analysis
    values = {side: [sum(by_env[name][side]["runs"][i] for name in COUNTS) / 6 for i in range(runs)]
              for side in ("native", "harbor")}
    native, harbor = summary(values["native"]), summary(values["harbor"])
    return {"schema_version": 1, "kind": "balrog_six_environment_parity_analysis", "analysis_only": True,
            "metric": "Arithmetic mean of six native environment progression means",
            "environment_weights": {name: 1/6 for name in COUNTS}, "episodes_per_suite_run": 255,
            "number_of_runs_per_side": runs, "native": native, "harbor": harbor,
            "run_score_ranges_overlap": native["max"] >= harbor["min"] and harbor["max"] >= native["min"],
            "environment_run_arrays": {name: {side: by_env[name][side]["runs"] for side in ("native", "harbor")} for name in COUNTS},
            "agent_model_settings": settings, "balrog_revision": revision,
            "runner_sha256": runner, "model_sdk_versions": sdk,
            "environment_manifest_sha256": {name: by_env[name]["manifest"]["sha256"] for name in COUNTS},
            "note": "Equal environment weights; never use the flat 255-trial Harbor mean. No approval or publication is implied."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.name == "parity_experiment.json":
        parser.error("Choose a new analysis output; formal results are assembled separately")
    try:
        result = aggregate([read_json(p) for p in args.analysis])
    except (ValidationError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")
    print(json.dumps({side: result[side] for side in ("native", "harbor")}, indent=2))


if __name__ == "__main__":
    main()
