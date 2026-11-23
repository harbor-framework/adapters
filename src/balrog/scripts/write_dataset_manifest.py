"""Prepare an unpublished dataset.toml with Harbor's canonical task digests."""

import argparse
import json
from pathlib import Path
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", choices=("full", "sanity", "parity"), default="full")
    parser.add_argument("--name", default="balrog/babyai")
    parser.add_argument("--environments", nargs="+", default=["babyai"])
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    import sys
    sys.path.insert(0, str(project / "src"))
    from balrog.suite import select_suite_cases
    cases = select_suite_cases(args.environments, args.split)
    ids = [case["episode"]["task_id"] for case in cases]
    env_names = sorted({case["episode"]["env_name"] for case in cases})
    present = {path.parent.name for path in args.dataset.glob("*/task.toml")}
    if present != set(ids):
        parser.error("Dataset does not exactly match the frozen split")
    for task_id in ids:
        config = tomllib.loads((args.dataset / task_id / "task.toml").read_text(encoding="utf-8"))
        if config.get("task", {}).get("name") != "balrog/" + task_id:
            parser.error("Task name missing or inconsistent: " + task_id)
    from harbor.cli.add import _resolve_local_task
    from harbor.models.dataset.manifest import DatasetInfo, DatasetManifest
    from harbor.models.task.config import Author

    result = DatasetManifest(
        dataset=DatasetInfo(
            name=args.name,
            description=(f"BALROG text-only adaptation: {len(ids)} fixed episodes across {', '.join(env_names)}. "
                         "Seeds are predetermined, not the upstream random evaluation distribution. "
                         "Adapter by QYechang; benchmark and games by their original contributors. "
                         "Model parity and registry publication are pending."),
            authors=[Author(name="QYechang"), Author(name="BALROG contributors"),
                     Author(name="Underlying game and benchmark contributors")],
            keywords=["balrog", *env_names, "text-only", "interactive"],
        ),
        tasks=[_resolve_local_task(args.dataset / task_id) for task_id in ids],
        metadata={"split": args.split, "parity_status": "not_run", "published": False},
    )
    output = args.dataset / "dataset.toml"
    output.write_text(result.to_toml(), encoding="utf-8", newline="\n")
    checked = DatasetManifest.from_toml_file(output)
    if checked.unique_task_count != len(ids):
        raise ValueError("Manifest did not preserve all unique task references")
    print(f"Prepared {output}: {checked.unique_task_count} local tasks; not published")


if __name__ == "__main__":
    main()
