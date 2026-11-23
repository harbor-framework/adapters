"""Generate and inspect the proposed ten-task sanity set without model execution.

This command reads public settings, archives pinned local sources and validates
Harbor configurations. It never reads credentials, builds/runs a container, or
calls a model. Output previews are preparation evidence, not approved jobs.
"""

import argparse
import json
from pathlib import Path
import sys

from parity_launch import (
    ENVIRONMENTS, PROJECT, build_harbor_job, file_sha256, harbor_version,
    load_settings, native_build_provenance, select_episodes, validate_dataset,
)
from native_daytona import preview as preview_native_daytona

sys.path.insert(0, str(PROJECT / "src"))
from balrog.adapter import BALROGAdapter, default_source_directory


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def task_inventory(path):
    """Bind every generated input, including oracle, grader and Docker context."""
    files = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink() or item.is_junction():
            raise ValueError("Generated inputs must not contain symlinks or junctions")
        if item.is_file():
            files[item.relative_to(path).as_posix()] = file_sha256(item)
    return files


def prepare(args):
    output = args.output_dir.expanduser().absolute()
    if output.exists():
        raise ValueError("Preparation directory already exists; use a new path to retain earlier evidence")
    if any(p.is_symlink() or p.is_junction() for p in (output, *output.parents)):
        raise ValueError("Preparation path must not traverse a symlink or junction")
    settings, settings_metadata = load_settings(args.settings)
    selected = {
        env: select_episodes(env, "sanity", selection_plan=args.selection_plan)
        for env in ENVIRONMENTS
    }
    ids = [e["task_id"] for episodes, _ in selected.values() for e in episodes]
    if len(ids) != len(set(ids)) or len(ids) != 10:
        raise ValueError("This preparation command requires the proposed ten unique sanity tasks")
    # Validate the installed JobConfig and version before creating any outputs.
    version = harbor_version()
    jobs = {
        env: {platform: build_harbor_job(
            dataset=output / "datasets" / env, settings_path=args.settings,
            model_id=settings["client"]["model_id"], jobs_dir=output / "jobs",
            job_name="sanity-" + env, concurrency=1, episode_timeout=None,
            environment_type=platform,
        ) for platform in ("docker", "daytona")} for env in ENVIRONMENTS
    }
    output.mkdir(parents=True)
    rows = []
    for env, (episodes, selection) in selected.items():
        dataset = output / "datasets" / env
        generated = BALROGAdapter(
            output_dir=dataset, environments=[env], split="sanity",
            task_ids=[e["task_id"] for e in episodes],
            benchmark_source=args.benchmark_source, minigrid_source=args.minigrid_source,
            assets_dir=args.assets_dir,
        ).run()
        if {p.name for p in generated} != {e["task_id"] for e in episodes}:
            raise ValueError("Generator did not retain the exact selected scope")
        tasks = validate_dataset(dataset, episodes)
        all_inputs = {task.name: task_inventory(task) for task in generated}
        environment_dir = dataset / episodes[0]["task_id"] / "environment"
        native = native_build_provenance(environment_dir, episodes)
        native_daytona = preview_native_daytona(environment_dir, episodes, settings, native, None)
        preview = {
            "status": "PREVIEW_ONLY_NOT_APPROVED_NOT_RUN",
            "model_execution_performed": False,
            "formal_timeout_seconds": None,
            "selection": selection, "settings": settings_metadata,
            "native_build": native, "generated_task_hashes": tasks,
            "native_daytona_preview": native_daytona,
            "generated_files_sha256": all_inputs,
            "harbor_version": version, "harbor_job_previews": jobs[env],
            "daytona_status": "CONFIGURATION_VALIDATED_REMOTE_RUNTIME_UNTESTED",
        }
        previews = output / "previews"
        previews.mkdir(exist_ok=True)
        write_json(previews / (env + ".json"), preview)
        rows.append({"environment": env, "task_ids": selection["task_ids"],
                     "episodes": len(episodes), "manifest_sha256": selection["manifest_sha256"],
                     "native_budget": selection["native_action_budget"],
                     "native_build_context_sha256": native["build_context_sha256"],
                     "preview": "previews/" + env + ".json"})
    receipt = {
        "status": "TEN_TASK_OFFLINE_PREPARATION_PASSED",
        "task_ids": ids, "episodes": len(ids), "environments": rows,
        "harbor_version": version, "selection_plan_sha256": file_sha256(args.selection_plan),
        "settings_file_sha256": settings_metadata["settings_file_sha256"],
        "model_api_calls": 0, "credentials_loaded": False,
        "containers_built_or_run": False, "parity_approved": False,
        "limitations": [
            "Configuration previews have no agreed execution timeout and must not be launched as formal jobs.",
            "This command does not validate game installation or gameplay; clean-build/reference evidence is separate.",
            "Daytona, provider model availability and paid experiments require their own approval and preflight.",
        ],
    }
    write_json(output / "preparation.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--selection-plan", type=Path, default=PROJECT / "parity/plan.proposed.json")
    parser.add_argument("--settings", type=Path, default=PROJECT / "parity/settings.proposed.json")
    parser.add_argument("--benchmark-source", type=Path, default=default_source_directory("BALROG"))
    parser.add_argument("--minigrid-source", type=Path, default=default_source_directory("minigrid-source"))
    parser.add_argument("--assets-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = prepare(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": receipt["status"], "episodes": receipt["episodes"],
                      "harbor_version": receipt["harbor_version"], "model_api_calls": 0,
                      "receipt": str(args.output_dir / "preparation.json")}, indent=2))


if __name__ == "__main__":
    main()
