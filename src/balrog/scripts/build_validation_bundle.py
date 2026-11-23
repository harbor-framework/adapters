#!/usr/bin/env python3
"""Package saved BALROG validation evidence, or check the committed summaries.

No game, Docker, network, model, or credential access. Rebuilding needs the
original development workspace; --check needs only this adapter checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

PROJECT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT / "src/balrog/fixtures"
OUTPUT = PROJECT / "validation"
ENVS = ("babyai", "babaisai", "textworld", "crafter", "minihack", "nle")
COUNTS = dict(zip(ENVS, (50, 120, 30, 10, 40, 5)))
FULL = dict(zip(ENVS, (50, 120, 30, 0, 39, 0)))
REPORTS = {
    "babyai": "research/babyai_oracle_full_validation.json",
    "babaisai": "research/babaisai_full_harbor_validation.json",
    "textworld": "research/textworld_full_harbor_validation.json",
    "crafter": "research/crafter_full_harbor_validation.json",
    "minihack_nle": "research/nle_minihack_full_harbor_validation.json",
}
JOBS = {
    "babyai": "babyai-full-oracle",
    "babaisai": "babaisai-full-oracle-v2",
    "textworld": "textworld-full-oracle-v2",
    "crafter": "crafter-full-reference",
    "minihack_nle": "nle-minihack-native-order",
}
REVIEW_BASE = "543861e1ad298c5d94f2480e9cbad74587041864"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select(data, keys):
    return {k: data[k] for k in keys.split() if k in data}


def fixture_path(env):
    return FIXTURES / ("manifest.json" if env == "babyai" else env + "_manifest.json")


def write(name, value):
    path = OUTPUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def score(value):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            "Nonfinite or out-of-range score")
    return value


def rebuild(workspace):
    workspace = workspace.resolve()
    source_inventory = []

    def inventory(relative):
        path = workspace / relative
        source_inventory.append({"workspace_relative_path": relative.replace("\\", "/"),
                                 "sha256": sha(path), "bytes": path.stat().st_size,
                                 "raw_artifact_packaged": False})
        return path

    def source(relative):
        path = inventory(relative)
        return read(path)

    saved = source("research/balrog_six_environment_validation.json")
    require(saved["selected_cases"] == 255 and saved["full_oracles"] == 239,
            "Unexpected saved baseline scope")
    fixtures = {e: read(fixture_path(e)) for e in ENVS}
    by_id = {}
    manifests = {}
    for env, manifest in fixtures.items():
        manifests[env] = {"path": fixture_path(env).relative_to(PROJECT).as_posix(),
                          "sha256": sha(fixture_path(env)),
                          "source_commits": manifest["source_commits"],
                          "count": len(manifest["cases"])}
        require(manifests[env]["sha256"] == saved["manifests"][env]["sha256"],
                "A baseline fixture changed: " + env)
        for case in manifest["cases"]:
            ep = case["episode"]
            require(ep["task_id"] not in by_id, "Duplicate task ID")
            by_id[ep["task_id"]] = (env, ep, case)

    baseline_cases, validators, jobs = [], {}, {}
    for group, relative in REPORTS.items():
        report = source(relative)
        job_dir = workspace / "research/harbor-jobs" / JOBS[group]
        job = source("research/harbor-jobs/" + JOBS[group] + "/result.json")
        job_hash = sha(job_dir / "result.json")
        if "job_result_sha256" in report:
            require(job_hash == report["job_result_sha256"], "Job result checksum mismatch")
        require(job["finished_at"] is not None, "Unfinished baseline job")
        stats = job["stats"]
        for key in ("n_errored_trials", "n_running_trials", "n_pending_trials", "n_cancelled_trials"):
            require(stats[key] == 0, "Baseline job not clean: " + key)
        require(job["n_total_trials"] == stats["n_completed_trials"] == len(report["checks"]),
                "Job coverage mismatch")
        raw_trials = {}
        snapshots = {}
        for trial_file in job_dir.glob("*/result.json"):
            verifier_file = trial_file.parent / "verifier/result.json"
            require(verifier_file.is_file(), "Missing verifier result")
            trial, result = read(trial_file), read(verifier_file)
            task_id = result["task_id"]
            require(task_id not in raw_trials, "Duplicate raw trial")
            require(trial["exception_info"] is None and trial["reward_valid"] is True,
                    "Invalid raw trial")
            require(trial["agent_info"]["name"] == "oracle", "Unexpected baseline agent")
            require(trial["config"]["job_id"] == job["id"], "Trial belongs to another job")
            task_path = Path(trial["config"]["task"]["path"].replace("\\", "/"))
            if not task_path.is_absolute():
                task_path = workspace / task_path
            env = by_id[task_id][0]
            snapshot = snapshots.setdefault(env, {})
            for filename in ("environment/game_server.py", "environment/Dockerfile",
                             "environment/Dockerfile.game", "environment/requirements-agent.lock",
                             "tests/verifier.py", "tests/test.sh", "task.toml"):
                path = task_path / filename
                if path.is_file():
                    snapshot.setdefault(filename, set()).add(sha(path))
            raw_trials[task_id] = (trial, result, trial_file, verifier_file)
        jobs[group] = {
            "source_id": "research/harbor-jobs/" + JOBS[group] + "/result.json",
            "sha256": job_hash, "job_id": job["id"],
            **select(job, "schema_version started_at finished_at n_total_trials"),
            "statistics": select(stats, "n_completed_trials n_errored_trials n_cancelled_trials n_running_trials n_pending_trials n_retries"),
            "generated_snapshot_file_hashes_observed_at_packaging": {
                env: {name: sorted(hashes) for name, hashes in files.items()}
                for env, files in snapshots.items()},
        }
        validator = select(report, "status count passed total split agent exceptions all_full_oracles by_environment note job_started_at_utc naive_timestamp_interpretation fixture_manifest_sha256 source_native_report_sha256")
        validator.update(source_id=relative, source_sha256=sha(workspace / relative),
                         job_result_sha256=job_hash, checks=[])
        for checked in report["checks"]:
            task_id = checked["task_id"]
            env, ep, fixture_case = by_id[task_id]
            trial, result, trial_file, verifier_file = raw_trials.pop(task_id)
            value = score(checked.get("progression", checked.get("reward")))
            require(result["progression"] == value and result["replay_progression"] == value,
                    "Saved checker and verifier disagree")
            require(result["replay_verified"] is True and result["finalized"] is True,
                    "Baseline reference lacks strict replay")
            require(result["steps"] == checked["steps"] == len(result["transitions"]),
                    "Saved step count mismatch")
            require(result["task"] == ep["task"] and result["seed"] == ep["seed"] and
                    result["max_steps"] == ep["expected_max_steps"] and
                    result["initial_observation_sha256"] == ep["expected_initial_observation_sha256"],
                    "Saved task identity differs from fixture")
            full = checked.get("full_oracle", True if env == "babyai" else False)
            require(full == (fixture_case.get("oracle") is not None), "Oracle classification mismatch")
            require(not full or value == 1, "A full oracle must score one")
            native_checked = checked.get("native_transitions_checked", checked.get("native_fixture_matched"))
            level = checked.get("validation_level", "native_transitions_and_server_replay")
            clean_check = {"task_id": task_id, "env_name": env, "progression": value,
                           "full_oracle": full, "steps": result["steps"], "replay_verified": True,
                           "native_transitions_checked": native_checked, "validation_level": level,
                           "legacy_reward_rounding": checked.get("legacy_reward_rounding", False)}
            validator["checks"].append(clean_check)
            baseline_cases.append({**clean_check, "task": ep["task"], "seed": ep["seed"],
                                   "max_steps": ep["expected_max_steps"],
                                   "initial_observation_sha256": ep["expected_initial_observation_sha256"],
                                   "terminated": result["terminated"], "truncated": result["truncated"],
                                   "job_group": group, "trial_id": trial["id"],
                                   "harbor_task_checksum": trial["task_checksum"],
                                   "raw_trial_result_sha256": sha(trial_file),
                                   "raw_verifier_result_sha256": sha(verifier_file)})
        require(not raw_trials, "Unaccounted baseline trials")
        validators[group] = validator

    baseline_cases.sort(key=lambda x: (ENVS.index(x["env_name"]), x["task_id"]))
    environment_counts = {}
    for env in ENVS:
        rows = [x for x in baseline_cases if x["env_name"] == env]
        environment_counts[env] = {"completed": len(rows), "full_oracles": sum(x["full_oracle"] for x in rows),
                                   "diagnostic_references": sum(not x["full_oracle"] for x in rows),
                                   "steps": sum(x["steps"] for x in rows),
                                   "mean_native_progression": statistics.mean(x["progression"] for x in rows)}
    write("baseline.json", {"schema_version": 1, "scope": "unchanged_fixed_255_case_offline_reference_baseline",
                            "evidence_kind": "saved_Harbor_results_and_saved_validator_reports",
                            "completed": len(baseline_cases), "infrastructure_errors": 0,
                            "full_oracles": 239, "diagnostic_references": 16,
                            "model_api_calls": 0, "model_parity_completed": False,
                            "all_oracle_requirement_met": False, "environments": environment_counts,
                            "cases": baseline_cases})
    write("validator_reports.json", {"schema_version": 1, "reports": validators,
                                     "limitation": "Saved checker outputs. Raw transitions, logs and generated task snapshots are not included. No independent gameplay rerun was performed while packaging."})

    mini = source("research/minihack_budget_proposal_harbor_validation.json")
    proof = source("research/minihack_oracle_audit_v2_proof.json")
    mini_clean = select(mini, "status job_result_sha256 completed_tasks full_score_tasks_in_proposal infrastructure_errors native_transitions_checked all_replays_verified unchanged_original_fixture_sha256 official_oracles_added model_api_calls rows")
    mini_clean.update(schema_version=1, proposal_approved=False, included_in_baseline=False,
                      budget_scope="Ten Boxoban cases use 200; the other thirty MiniHack cases retain 100.",
                      proof=proof)
    write("proposals/minihack_200.json", mini_clean)

    private = source("research/crafter_private_harbor_full_validation.json")
    boundary = source("research/crafter_private_full_docker_boundary.json")
    private_trial = workspace / private["trial"].replace("\\", "/")
    for filename, digest in private["artifact_sha256"].items():
        require(sha(private_trial / filename.replace("\\", "/")) == digest,
                "Private prototype raw artifact checksum mismatch")
    private_result = read(private_trial / "verifier/result.json")
    require(private_result["progression"] == private["native_progression"] == 1 and
            private_result["steps"] == private["steps"] == 725 and
            private_result["replay_verified"] is False and
            private_result["scoring_mode"] == "authoritative_native_state",
            "Private prototype result differs from saved checker")
    private_clean = select(private, "status job_id job_finished one_completed_trial_zero_errors trial_job_and_task_identity_checked reward_valid job_trial_time_order_utc naive_job_time_offset harbor_task_name host_agent native_seed native_budget controller_limit steps native_progression controller_snapshot_native_progression verifier_progression harbor_reward all_actions_match_authoritative_log source_and_critical_game_files_unchanged game_permissions_checked normal_container_isolation_verified_after_controller host_agent_sha256 controller_error missing_achievements terminated truncated replay_verified replay_diagnostic full_oracle_available model_api_calls artifact_sha256")
    private_clean.update(schema_version=1, included_in_baseline=False, proposal_approved=False,
                         scoring_mode=private_result["scoring_mode"],
                         isolation_checks=select(boundary, "checks_passed game_has_no_shared_mounts separate_pid_and_ipc_namespaces no_host_ports"),
                         interpretation="One privileged adaptive-controller Harbor trial, seed 6. The native score is 1, but fresh action replay diverges. This is neither an approved full oracle nor model parity; the private controller is not packaged.")
    private_clean["artifact_sha256"] = {name.replace("\\", "/"): digest for name, digest in private["artifact_sha256"].items()}
    write("diagnostics/crafter_private_seed6.json", private_clean)

    tactics = source("research/crafter_v4_tactics_audit.json")
    # The audited output contains no host paths or configuration values.
    tactics_clean = {k: v for k, v in tactics.items() if k != "rows"}
    tactics_clean.update(schema_version=1, included_in_baseline=False,
                         rows=[select(r, "seed achievements progression steps terminated truncated budget_exhausted missing error tactical_decisions simulation_steps hp_prediction_mismatches elapsed_seconds") for r in tactics["rows"]])
    write("diagnostics/crafter_tactics.json", tactics_clean)

    nle = source("research/nle_oracle_audit_v2_proof/report.json")
    nle.pop("candidate_patch")
    nle.update(schema_version=1, included_in_baseline=False, candidate_approved=False,
               candidate_applied_to_benchmark=False,
               interpretation="Source-derived scorer ceiling and synthetic boundary/unit checks, not a game trajectory attaining that ceiling or ascension.",
               source_url="https://github.com/balrog-ai/BALROG/blob/" + nle["balrog_pin"] + "/balrog/environments/nle/progress.py")
    write("diagnostics/nle_ceiling.json", nle)

    # Hash-only references support the source-focused review documents without
    # publishing trajectories, controllers or host-local details.
    inventory("research/crafter_determinism_report.json")
    inventory("research/minihack_zero_all.json")
    inventory("research/balrog_submission_packaging.json")
    inventory("research/balrog_submission_structure.json")
    submission = source("research/balrog_submission_checks.json")
    logs = ["balrog_submission_unittest_final.log"] + ["submission_" + name + ".py.log" for name in
            ("test_runtime", "test_parity", "test_native_batch", "test_crafter_failure_policy", "test_suite_verification", "test_bridge")]
    for name in logs:
        path = inventory("research/" + name)
        log = path.read_text(encoding="utf-8", errors="replace")
        matches = list(re.finditer(r"Ran (\d+) tests? in ([\d.]+)s\s+OK(?: \(skipped=(\d+)\))?", log))
        require(len(matches) == 1, "No unambiguous successful test footer: " + name)
        count, seconds, skipped = matches[0].groups()
        row = submission["unit"] if name == logs[0] else submission["runtime"][name.removeprefix("submission_").removesuffix(".log")]
        require(row["total"] == int(count) and row["skipped"] == int(skipped or 0) and
                row["passed"] == int(count) - int(skipped or 0) and row["saved_log_sha256"] == sha(path),
                "Submission report differs from test log: " + name)
    # Keep warning identities and locations; omit prose containing the scanner's
    # generic Windows absolute-path example, rather than relaxing sanitization.
    submission["structural_validator"]["warnings"] = [select(row, "level check file line")
        for row in submission["structural_validator"]["warnings"]]
    submission.update(schema_version=1, evidence_kind="saved_test_and_packaging_reports_no_gameplay_rerun")
    write("submission_checks.json", submission)

    runtime_paths = sorted((PROJECT / "src/balrog/runtime-dockerfiles").glob("*.Dockerfile"))
    runtime_paths += sorted((PROJECT / "src/balrog/task-template").rglob("*.py"))
    runtime_paths += [PROJECT / "src/balrog/task-template/environment/Dockerfile",
                      PROJECT / "src/balrog/task-template/environment/Dockerfile.game",
                      PROJECT / "src/balrog/task-template/environment/requirements-agent.lock",
                      FIXTURES / "textworld_requirements.lock", PROJECT / "scripts/check_suite_reference.py",
                      PROJECT / "scripts/check_oracle.py", PROJECT / "scripts/build_validation_bundle.py"]
    runtime_files = {p.relative_to(PROJECT).as_posix(): sha(p) for p in runtime_paths if p.is_file()}
    runtime_sources = read(FIXTURES / "runtime_sources.json")
    for rows in runtime_sources.values():
        for row in rows:
            row.pop("path", None)
    write("provenance.json", {
        "schema_version": 1, "repository_review_base": {"repository": "https://github.com/harbor-framework/adapters",
            "commit": REVIEW_BASE, "meaning": "Current PR review base; not the execution commit of earlier experiments."},
        "historical_execution_adapter_commit": None,
        "historical_execution_commit_limitation": "The local uncommitted adapter had no recorded git commit for these experiments. Raw Harbor task checksums and saved report hashes are retained. Generated snapshot byte hashes were observed during packaging and are not independently attested execution image digests.",
        "recorded_baseline_summary_runtime_sha256": saved["final_runtime_sha256"],
        "recorded_baseline_runtime_meaning": "Value saved by the six-environment summary; individual jobs used earlier generated snapshots and this is not asserted to be their common runtime hash.",
        "review_snapshot_file_sha256": runtime_files,
        "runtime_pins": {"harbor_reported_version": "0.26.0", "python_image": "python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370",
                         "crafter": "1.8.3", "balrog-nle": "0.9.0",
                         "limitation": "Source/build pins and saved task snapshots, not a complete runtime SBOM or attested image inventory."},
        "fixture_manifests": manifests, "runtime_source_archives": runtime_sources,
        "baseline_jobs": jobs, "raw_source_inventory": source_inventory,
        "packaging": {"gameplay_rerun": False, "paid_api_calls": 0, "raw_jobs_uploaded": False,
                       "game_assets_uploaded": False, "research_controllers_uploaded": False,
                       "sanitization": "Explicit field selection; excludes host absolute paths, environment values, grading credentials, generated Compose files and private controllers."}})
    checksums = {p.relative_to(OUTPUT).as_posix(): sha(p) for p in sorted(OUTPUT.rglob("*"))
                 if p.is_file() and p.name != "checksums.json"}
    write("checksums.json", {"schema_version": 1, "sha256": checksums,
                             "meaning": "Integrity cross-check only, not an external signature or gameplay reproduction."})


def check(*, historical=False):
    checksum = read(OUTPUT / "checksums.json")["sha256"]
    actual = {p.relative_to(OUTPUT).as_posix() for p in OUTPUT.rglob("*")
              if p.is_file() and p.name != "checksums.json"}
    require(actual == set(checksum), "Bundle file coverage differs from checksum inventory")
    forbidden = [r"\b[A-Za-z]:[\\/]", r"\\\\[A-Za-z]", r"/Users/[^/]+/", r"/home/[^/]+/",
                 r"RESULT_TOKEN", r"(?i)Bearer\s+[A-Za-z0-9._-]{12,}", r"\bsk-[A-Za-z0-9_-]{12,}"]
    for name, expected in checksum.items():
        path = OUTPUT / name
        require(sha(path) == expected, "Bundle checksum mismatch: " + name)
        require(path.stat().st_size < 1_000_000, "Unexpectedly large bundle file")
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            require(re.search(pattern, text) is None, "Potential private path/credential in " + name)
    baseline = read(OUTPUT / "baseline.json")
    provenance = read(OUTPUT / "provenance.json")
    review_drift = []
    for name, expected in provenance["review_snapshot_file_sha256"].items():
        current = sha(PROJECT / name) if (PROJECT / name).is_file() else None
        if current != expected:
            review_drift.append({"file": name, "historical_sha256": expected, "current_sha256": current})
    require(historical or not review_drift,
            "Current review files differ from bundle snapshot. Use --check --historical only to audit "
            "the archived evidence; it does not validate the changed runtime. Changed files: " +
            ", ".join(row["file"] for row in review_drift))
    rows = baseline["cases"]
    require(len(rows) == baseline["completed"] == 255 and len({r["task_id"] for r in rows}) == 255,
            "Baseline task coverage mismatch")
    require(sum(r["full_oracle"] for r in rows) == baseline["full_oracles"] == 239 and
            baseline["diagnostic_references"] == 16, "Full/diagnostic counts changed")
    require(baseline["model_api_calls"] == 0 and baseline["model_parity_completed"] is False and
            baseline["all_oracle_requirement_met"] is False, "Misleading completion claim")
    by_id = {r["task_id"]: r for r in rows}
    for env in ENVS:
        manifest = read(fixture_path(env))
        pin = provenance["fixture_manifests"][env]
        require(sha(fixture_path(env)) == pin["sha256"] and manifest["source_commits"] == pin["source_commits"],
                "Fixture source pin/hash differs from saved evidence")
        selected = [r for r in rows if r["env_name"] == env]
        expected_ids = {c["episode"]["task_id"] for c in manifest["cases"]}
        require({r["task_id"] for r in selected} == expected_ids and len(selected) == COUNTS[env],
                "Missing or substituted fixed cases: " + env)
        aggregate = baseline["environments"][env]
        require(aggregate["completed"] == COUNTS[env] and aggregate["full_oracles"] == FULL[env] and
                aggregate["diagnostic_references"] == COUNTS[env] - FULL[env] and
                aggregate["steps"] == sum(r["steps"] for r in selected) and
                aggregate["mean_native_progression"] == statistics.mean(r["progression"] for r in selected),
                "Environment aggregate mismatch")
        for case in manifest["cases"]:
            ep = case["episode"]
            row = by_id[ep["task_id"]]
            score(row["progression"])
            require(row["seed"] == ep["seed"] and row["task"] == ep["task"] and
                    row["max_steps"] == ep["expected_max_steps"] and
                    row["initial_observation_sha256"] == ep["expected_initial_observation_sha256"], "Case identity mismatch")
            require(row["replay_verified"] is True and 0 <= row["steps"] <= row["max_steps"], "Invalid baseline replay/steps")
            require(row["full_oracle"] == (case.get("oracle") is not None), "Oracle status mismatch")
            reference = case.get("oracle") or case.get("reference")
            require(reference is not None and row["progression"] == reference["expected_progression"],
                    "Native fixture and score disagree")
    validators = read(OUTPUT / "validator_reports.json")["reports"]
    checked_ids = []
    for report in validators.values():
        for row in report["checks"]:
            checked_ids.append(row["task_id"])
            require(all(by_id[row["task_id"]][key] == value for key, value in row.items()),
                    "Saved validator differs from baseline row")
    require(set(checked_ids) == set(by_id) and len(checked_ids) == 255, "Validator coverage mismatch")
    mini = read(OUTPUT / "proposals/minihack_200.json")
    require(mini["proposal_approved"] is False and mini["included_in_baseline"] is False and
            mini["official_oracles_added"] == 0, "Proposal promoted into baseline")
    require(len(mini["rows"]) == mini["completed_tasks"] == mini["full_score_tasks_in_proposal"] == 40 and
            sum(r["steps"] for r in mini["rows"]) == mini["native_transitions_checked"] == 1531,
            "Proposal coverage/transition mismatch")
    require({r["task_id"] for r in mini["rows"]} == {r["task_id"] for r in rows if r["env_name"] == "minihack"},
            "Proposal substituted task IDs")
    for row in mini["rows"]:
        require(row["progression"] == 1 and row["replay_verified"] is True and
                row["proposal_budget"] == (200 if "boxoban" in row["task_id"] else 100), "Proposal score/budget mismatch")
    require(mini["proof"]["abstract_proof"]["minimum_unit_actions"] == 104 and
            mini["proof"]["native_budget"] == 100, "Budget proof mismatch")
    private = read(OUTPUT / "diagnostics/crafter_private_seed6.json")
    require(private["native_seed"] == 6 and private["native_budget"] == 2000 and private["steps"] == 725 and
            private["native_progression"] == private["harbor_reward"] == 1 and private["replay_verified"] is False and
            private["full_oracle_available"] is False and private["included_in_baseline"] is False and
            private["proposal_approved"] is False, "Private prototype scope/score mismatch")
    tactics = read(OUTPUT / "diagnostics/crafter_tactics.json")
    require(len(tactics["rows"]) == 10 and {r["seed"] for r in tactics["rows"]} == set(range(10)) and
            sum(r["steps"] for r in tactics["rows"]) == tactics["total_live_actions"] == 9791 and
            sum(r["progression"] == 1 for r in tactics["rows"]) == tactics["native_full_successes"] == 0,
            "Negative tactic coverage mismatch")
    for row in tactics["rows"]:
        require(score(row["progression"]) == row["achievements"] / 22 and row["steps"] <= 2000,
                "Tactic native score/budget mismatch")
    nle = read(OUTPUT / "diagnostics/nle_ceiling.json")
    require(nle["syntactic_tight_upper_bound"] == 0.8067964442444019 and nle["game_ascensions_obtained"] == 0 and
            nle["candidate_applied_to_benchmark"] is False, "NLE proof scope mismatch")
    submission = read(OUTPUT / "submission_checks.json")
    structure = submission["structural_validator"]
    require(submission["status"] == "OFFLINE_SUBMISSION_CHECKS_WITH_DISCLOSED_PARITY_VALIDATOR_GAP" and
            submission["unit"]["total"] == 54 and submission["unit"]["passed"] == 53 and
            submission["unit"]["skipped"] == 1 and submission["runtime_passed"] == 44 and
            sum(r["passed"] for r in submission["runtime"].values()) == 44 and
            len(structure["passed"]) == 29 and len(structure["errors"]) == 1 and
            len(structure["warnings"]) == 2 and submission["packaging"]["wheel_module_files_checked"] == 37 and
            {r["environment"] for r in submission["packaging"]["cases"]} == set(ENVS) and
            submission["docker_gameplay_rerun"] is False and submission["model_api_calls"] == 0,
            "Submission check counts or scope mismatch")
    print(json.dumps({"status": "passed", "kind": "saved_summary_integrity_not_gameplay_reproduction",
                      "historical_mode": historical, "review_snapshot_matches_current": not review_drift,
                      "review_snapshot_differences": review_drift,
                      "cases": len(rows), "full_oracles": 239, "diagnostics": 16,
                      "files": len(actual) + 1,
                      "bytes": sum(p.stat().st_size for p in OUTPUT.rglob("*") if p.is_file())}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed summaries without raw development artifacts")
    parser.add_argument("--historical", action="store_true",
                        help="Audit archived summaries while reporting source drift; does not validate the changed runtime")
    parser.add_argument("--workspace-root", type=Path, help="Rebuild from the original saved research workspace; no gameplay")
    args = parser.parse_args()
    if args.historical and (not args.check or args.workspace_root is not None):
        parser.error("--historical requires --check and cannot rebuild evidence")
    if args.workspace_root is not None:
        rebuild(args.workspace_root)
    elif not args.check:
        parser.error("Pass --check or --workspace-root")
    check(historical=args.historical)


if __name__ == "__main__":
    main()
