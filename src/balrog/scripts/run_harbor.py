"""Launch one complete Harbor model run without writing credentials into its config."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_native import PACKAGE, PROJECT, load_model_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--split", choices=("sanity", "full", "parity"), default="sanity")
    parser.add_argument("--environment", choices=("babyai", "babaisai", "textworld", "crafter", "nle", "minihack"), default="babyai")
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env.local")
    parser.add_argument("--harbor-python", default=sys.executable, help="Python with Harbor 0.26.0 installed")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--episode-timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.concurrency < 1 or args.episode_timeout < 1:
        parser.error("Concurrency and timeout must be positive")
    if not args.job_name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in args.job_name):
        parser.error("Use a simple unique job name containing letters, numbers, hyphens or underscores")
    manifest_name = "manifest.json" if args.environment == "babyai" else args.environment + "_manifest.json"
    manifest = json.loads((PACKAGE / "fixtures" / manifest_name).read_text(encoding="utf-8"))
    selected = [item["episode"]["task_id"] for item in manifest["cases"]
                if args.split != "sanity" or item["episode"]["seed"] == 0]
    present = {path.parent.name for path in args.dataset.glob("*/task.toml")}
    if present != set(selected):
        parser.error("Dataset directory does not exactly match the preselected manifest split")
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    model = settings.get("client", {}).get("model_id", "")
    job = {
        "job_name": args.job_name,
        "jobs_dir": str(args.jobs_dir.resolve()),
        "n_attempts": 1,
        "orchestrator": {"type": "local", "n_concurrent_trials": args.concurrency},
        "environment": {"type": "docker", "delete": True, "kwargs": {"auto_mounting": False}},
        "agents": [{"import_path": "balrog.agent:BalrogNativeAgent", "model_name": model,
                    "skip_model_parsing": True, "override_timeout_sec": args.episode_timeout,
                    "kwargs": {"settings_path": str(args.settings.resolve()),
                               "execution_timeout_sec": args.episode_timeout}}],
        "datasets": [{"path": str(args.dataset.resolve())}],
    }
    if args.dry_run:
        print(json.dumps(job, indent=2))
        return
    if not model or "REPLACE_" in model:
        parser.error("An exact team-confirmed model ID is required")
    job_dir = args.jobs_dir / args.job_name
    if job_dir.exists():
        parser.error("Job already exists; use a new name to preserve all attempts")
    environment = dict(os.environ, OPENAI_API_KEY=load_model_key(args.env_file),
                       PYTHONPATH=str(PROJECT / "src"), PYTHONUTF8="1")
    with tempfile.TemporaryDirectory(prefix="balrog-harbor-config-") as temporary:
        config = Path(temporary) / "job.json"
        config.write_text(json.dumps(job, indent=2), encoding="utf-8")
        subprocess.run([args.harbor_python, "-m", "harbor.cli.main", "run", "-c", str(config)],
                       env=environment, check=True)
    result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    if not result.get("finished_at") or result["stats"]["n_errored_trials"] or result["stats"]["n_completed_trials"] != len(selected):
        raise RuntimeError("Harbor run is incomplete or contains infrastructure errors; it is not a parity result")


if __name__ == "__main__":
    main()
