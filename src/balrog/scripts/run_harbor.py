"""Launch one complete Harbor model run without writing credentials into its config."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_native import PACKAGE, PROJECT, load_model_key
from parity_launch import (ENVIRONMENTS, build_harbor_job, file_sha256, harbor_version,
                           load_settings, select_episodes, validate_dataset, validate_timeout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--split", choices=("sanity", "full", "parity"), default="sanity",
                        help="Without an explicit selector, sanity means every seed-0 task type (58 overall)")
    parser.add_argument("--environment", choices=ENVIRONMENTS, default="babyai")
    parser.add_argument("--environment-type", choices=("docker", "daytona"), default="docker",
                        help="Harbor provider; Daytona configuration can be previewed without credentials")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--selection-plan", type=Path, help="Validate and select from the six-environment parity plan")
    selection.add_argument("--task-ids-file", type=Path, help="JSON list of task IDs within this environment/split")
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env.local")
    parser.add_argument("--harbor-python", default=sys.executable, help="Must match the current interpreter, which validates JobConfig")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--episode-timeout", type=int, help="Explicit remote episode seconds, required for live execution")
    parser.add_argument("--collection-grace", type=int, default=120, help="Additional outer agent seconds for collecting artifacts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        timing = validate_timeout(args.episode_timeout, dry_run=args.dry_run)
        if Path(args.harbor_python).resolve() != Path(sys.executable).resolve():
            raise ValueError("Run this script with the intended Harbor Python; validation and execution must use the same interpreter")
        episodes, plan = select_episodes(args.environment, args.split, selection_plan=args.selection_plan,
                                        task_ids_file=args.task_ids_file)
        _, settings_metadata = load_settings(args.settings)
        task_inputs = validate_dataset(args.dataset, episodes)
        job = build_harbor_job(dataset=args.dataset, settings_path=args.settings,
                               model_id=settings_metadata["model_id"], jobs_dir=args.jobs_dir,
                               job_name=args.job_name, concurrency=args.concurrency,
                               episode_timeout=args.episode_timeout, collection_grace=args.collection_grace,
                               environment_type=args.environment_type)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    plan.update(**timing, **settings_metadata, side="harbor", dry_run=args.dry_run,
                harbor_version=harbor_version(), launcher_sha256=file_sha256(Path(__file__)),
                runner_sha256=file_sha256(PACKAGE / "parity_runner.py"), task_inputs=task_inputs,
                collection_grace_seconds=args.collection_grace,
                environment_type=args.environment_type,
                platform_note=("Daytona options/schema validated only; remote runtime remains untested"
                               if args.environment_type == "daytona" else "Local Docker provider selected"),
                outer_agent_timeout_sec=job["agents"][0]["override_timeout_sec"])
    if args.dry_run:
        print(json.dumps({"plan": plan, "job": job}, indent=2))
        return
    job_dir = args.jobs_dir / args.job_name
    if job_dir.exists():
        parser.error("Job already exists; use a new name to preserve all attempts")
    environment = dict(os.environ, OPENAI_API_KEY=load_model_key(args.env_file),
                       PYTHONPATH=str(PROJECT / "src"), PYTHONUTF8="1")
    args.jobs_dir.mkdir(parents=True, exist_ok=True)
    # This sibling survives an interrupted launch without pre-creating Harbor's job.
    with (args.jobs_dir / (args.job_name + ".launch-plan.json")).open("x", encoding="utf-8") as handle:
        json.dump({"plan": plan, "job": job}, handle, indent=2)
    with tempfile.TemporaryDirectory(prefix="balrog-harbor-config-") as temporary:
        config = Path(temporary) / "job.json"
        config.write_text(json.dumps(job, indent=2), encoding="utf-8")
        subprocess.run([args.harbor_python, "-m", "harbor.cli.main", "run", "-c", str(config)],
                       env=environment, check=True)
    result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    if (not result.get("finished_at") or result["stats"]["n_errored_trials"]
            or result["stats"].get("n_retries", 0) or result["stats"]["n_completed_trials"] != len(episodes)):
        raise RuntimeError("Harbor run is incomplete or contains infrastructure errors; it is not a parity result")


if __name__ == "__main__":
    main()
