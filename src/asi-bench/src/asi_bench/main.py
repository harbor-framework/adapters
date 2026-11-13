from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from . import adapter


def _harborize(path: Path) -> None:
    import yaml
    task_md = path / "task.md"
    raw = task_md.read_text(encoding="utf-8")
    _, front, prompt = raw.split("---", 2)
    fm = yaml.safe_load(front) or {}
    meta = fm.get("metadata", {})
    toml = f'''version = "1.0"\n\n[task]\nname = "{meta["task_id"]}/b{meta["prompt_level"].lower()[1:]}"\nauthors = [{{ name = "ASI-Bench authors" }}]\n\n[metadata]\ndifficulty = "hard"\ncategory = "science"\ntags = ["asi-bench", "seed31415", "non-official"]\n\n[agent]\ntimeout_sec = {fm.get("agent", {}).get("timeout_sec", 3600)}\n\n[verifier]\ntimeout_sec = {fm.get("verifier", {}).get("timeout_sec", 900)}\n\n[environment]\ncpus = 2\nmemory_mb = 4096\nstorage_mb = 10240\n'''
    (path / "task.toml").write_text(toml)
    (path / "instruction.md").write_text(prompt.strip() + "\n")
    verifier = path / "verifier"
    tests = path / "tests"
    shutil.move(str(verifier), str(tests))
    score = tests / "score_entry.py"
    score.write_text(score.read_text().replace('Path("/verifier")', 'Path("/tests")'))
    sol = path / "solution"
    sol.mkdir()
    (sol / "solve.sh").write_text("#!/bin/sh\nexit 0\n")
    (sol / "solve.sh").chmod(0o755)
    task_md.unlink()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--source-dir", type=Path)
    p.add_argument("--task-ids")
    p.add_argument("--levels")
    p.add_argument("--limit", type=int)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    ids = args.task_ids.split(",") if args.task_ids else None
    levels = args.levels.split(",") if args.levels else None
    with tempfile.TemporaryDirectory() as tmp:
        generated = adapter.convert_all(args.source_dir, Path(tmp), overwrite=True, limit=args.limit, task_ids=ids, levels=levels)
        for src in generated:
            dst = args.output_dir / src.name
            if dst.exists() and args.overwrite:
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            _harborize(dst)
    print(json.dumps({"generated": len(generated), "output_dir": str(args.output_dir)}))

if __name__ == "__main__":
    main()
