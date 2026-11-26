"""Generate ControlArena datasets from a checkout of the Harbor adapters repository."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGES = Path(__file__).resolve().parents[1] / "src"
# Each entry is an independently locked Harbor adapter. The source setting names
# are the identifiers used by ControlArena 20.1.1.
ADAPTERS = {
    "agentdojo": "control-arena-agentdojo-honest",
    "apps": "control-arena-apps-honest",
    "bash": "control-arena-bash-honest",
    "bigcodebench": "control-arena-bigcodebench-honest",
    "iac": "control-arena-iac-honest",
    "iac_fast": "control-arena-iac-honest",
    "sae_interp_sabotage": "control-arena-sae-interp",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--list", action="store_true", help="List available generators")
    selection.add_argument("--settings", nargs="+", choices=ADAPTERS, metavar="SETTING",
                           help="Generate the named settings (see --list)")
    selection.add_argument("--all-supported", action="store_true",
                           help="Generate every setting that has a Harbor adapter")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/control-arena"),
                        help="Parent directory for the per-setting datasets")
    parser.add_argument("--limit", type=int, help="Maximum number of tasks per setting")
    parser.add_argument("--task-ids", nargs="+", help="Select cases within a single setting")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing tasks")
    args = parser.parse_args(argv)
    if args.list:
        for setting, package in ADAPTERS.items():
            print(f"{setting}\t{package}")
        return 0

    settings = list(ADAPTERS) if args.all_supported else list(dict.fromkeys(args.settings))
    if args.task_ids and len(settings) != 1:
        parser.error("--task-ids requires a single setting")
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be nonnegative")
    uv = shutil.which("uv")
    if uv is None:
        parser.error("Install uv and ensure it is on PATH")

    output = args.output_dir.resolve()
    for setting in settings:
        package = ADAPTERS[setting]
        command = [uv, "run", "--locked", package, "--output-dir", str(output / setting)]
        if setting in ("iac", "iac_fast"):
            command.extend(["--setting", setting])
        if args.limit is not None:
            command.extend(["--limit", str(args.limit)])
        if args.task_ids:
            command.extend(["--task-ids", *args.task_ids])
        if args.overwrite:
            command.append("--overwrite")
        result = subprocess.run(command, cwd=PACKAGES / package)
        if result.returncode:
            print(f"Generation failed for {setting} (exit {result.returncode}).", file=sys.stderr)
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
