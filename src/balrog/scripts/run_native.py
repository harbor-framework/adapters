"""Run the original agent/environment in the same pinned image as Harbor's game."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from parity_launch import (ENVIRONMENTS, PACKAGE, PROJECT, file_sha256, load_settings,
                           native_build_provenance, select_episodes, validate_timeout)


def load_model_key(path):
    """Read only the inference credential; never execute a shell or print it."""
    key = os.environ.get("OPENAI_API_KEY")
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name == "OPENAI_API_KEY":
                key = value.strip().strip("\"'") or key
    if not key:
        raise ValueError("Set OPENAI_API_KEY in the environment or the ignored .env.local file")
    return key


def mount(path, target, readonly=False):
    path = str(path.resolve())
    if "," in path:
        raise ValueError("Docker bind-mount paths must not contain a comma")
    return "type=bind,source=" + path + ",target=" + target + (",readonly" if readonly else "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-dir", type=Path, required=True, help="A generated task's environment directory")
    parser.add_argument("--settings", type=Path, required=True, help="Nonsecret, team-confirmed settings JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for this one native run")
    parser.add_argument("--split", choices=("sanity", "full", "parity"), default="sanity",
                        help="Without an explicit selector, sanity means every seed-0 task type (58 across six environments)")
    parser.add_argument("--environment", choices=ENVIRONMENTS, default="babyai")
    parser.add_argument("--environment-type", choices=("docker", "daytona"), default="docker",
                        help="Native executor; Daytona credentials use the live process environment")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--selection-plan", type=Path, help="Validate and select from the six-environment parity plan")
    selection.add_argument("--task-ids-file", type=Path, help="JSON list of task IDs within this environment/split")
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env.local")
    parser.add_argument("--episode-timeout", type=int, help="Explicit outer episode seconds, required for live execution")
    parser.add_argument("--dry-run", action="store_true", help="Show selected task IDs; do not build or call the API")
    args = parser.parse_args(argv)
    try:
        timing = validate_timeout(args.episode_timeout, dry_run=args.dry_run)
        episodes, plan = select_episodes(args.environment, args.split, selection_plan=args.selection_plan,
                                        task_ids_file=args.task_ids_file)
        settings, settings_metadata = load_settings(args.settings)
        build = native_build_provenance(args.environment_dir, episodes)
        cloud = None
        if args.environment_type == "daytona":
            from native_daytona import preview
            cloud = preview(args.environment_dir, episodes, settings, build, args.episode_timeout)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    plan.update(**timing, **settings_metadata, **build, side="native", dry_run=args.dry_run,
                environment_type=args.environment_type,
                launcher_sha256=file_sha256(Path(__file__)),
                selection_helper_sha256=file_sha256(PROJECT / "scripts/parity_launch.py"),
                runner_sha256=file_sha256(PACKAGE / "parity_runner.py"),
                batch_sha256=file_sha256(PACKAGE / "native_batch.py"))
    if cloud is not None:
        plan["daytona"] = cloud
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    if args.output_dir.exists():
        parser.error("Output directory already exists; use a new directory to preserve all attempts")
    if cloud is not None:
        from native_daytona import run_live
        key = load_model_key(args.env_file)
        args.output_dir.mkdir(parents=True)
        (args.output_dir / "run_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        run_live(args.environment_dir, args.output_dir, episodes, settings, cloud, key)
        return
    child_env = dict(os.environ, OPENAI_API_KEY=load_model_key(args.env_file))
    image = build["image"]
    subprocess.run(["docker", "build", "-f", str(args.environment_dir / "Dockerfile.game"),
                    "-t", image, str(args.environment_dir)], check=True)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "run_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="balrog-native-input-") as temporary:
        inputs = Path(temporary)
        (inputs / "episodes.json").write_text(json.dumps(episodes), encoding="utf-8")
        (inputs / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        command = ["docker", "run", "--rm", "--user", "0", "--env", "OPENAI_API_KEY",
                   "--mount", mount(PACKAGE, "/opt/parity", True),
                   "--mount", mount(inputs, "/input", True),
                   "--mount", mount(args.output_dir, "/results"), image,
                   "python", "/opt/parity/native_batch.py", "--episodes", "/input/episodes.json",
                   "--settings", "/input/settings.json", "--output-dir", "/results",
                   "--episode-timeout", str(args.episode_timeout)]
        subprocess.run(command, env=child_env, check=True)


if __name__ == "__main__":
    main()
