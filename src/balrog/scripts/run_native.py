"""Run the original agent/environment in the same pinned image as Harbor's game."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / "src/balrog"


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-dir", type=Path, required=True, help="A generated task's environment directory")
    parser.add_argument("--settings", type=Path, required=True, help="Nonsecret, team-confirmed settings JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for this one native run")
    parser.add_argument("--split", choices=("sanity", "full", "parity"), default="sanity")
    parser.add_argument("--environment", choices=("babyai", "babaisai", "textworld", "crafter", "nle", "minihack"), default="babyai")
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env.local")
    parser.add_argument("--episode-timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true", help="Show selected task IDs; do not build or call the API")
    args = parser.parse_args()
    manifest_path = PACKAGE / "fixtures" / ("manifest.json" if args.environment == "babyai" else args.environment + "_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = [item["episode"]["task_id"] for item in manifest["cases"]
                if args.split != "sanity" or item["episode"]["seed"] == 0]
    cases = {item["episode"]["task_id"]: item["episode"] for item in manifest["cases"]}
    episodes = [cases[task_id] for task_id in selected]
    plan = {"split": args.split, "task_ids": selected, "episodes": len(episodes),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "episode_timeout_sec": args.episode_timeout}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    image_episode = json.loads((args.environment_dir / "episode.json").read_text())
    if image_episode.get("env_name", "babyai") != args.environment:
        parser.error("Generated image belongs to a different environment")
    if args.output_dir.exists():
        parser.error("Output directory already exists; use a new directory to preserve all attempts")
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    model = settings.get("client", {}).get("model_id", "")
    if not model or "REPLACE_" in model:
        parser.error("An exact team-confirmed model ID is required")
    child_env = dict(os.environ, OPENAI_API_KEY=load_model_key(args.env_file))
    # This tag is based on public build inputs, not on the inference credential.
    image_digest = hashlib.sha256()
    build_inputs = ["Dockerfile.game", "requirements-agent.lock", "game_server.py", "episode.json"]
    build_inputs += [p.relative_to(args.environment_dir).as_posix() for p in sorted((args.environment_dir / "vendor").rglob("*")) if p.is_file()]
    if (args.environment_dir / "requirements-game.lock").exists():
        build_inputs.append("requirements-game.lock")
    for relative in build_inputs:
        image_digest.update(relative.encode())
        image_digest.update((args.environment_dir / relative).read_bytes())
    image = "harbor-balrog-native:" + image_digest.hexdigest()[:16]
    subprocess.run(["docker", "build", "-f", str(args.environment_dir / "Dockerfile.game"),
                    "-t", image, str(args.environment_dir)], check=True)
    args.output_dir.mkdir(parents=True)
    plan.update(image=image, model_id=model, settings_file_sha256=hashlib.sha256(args.settings.read_bytes()).hexdigest())
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
