"""CLI entry point for generating TwinEnv-Bench Harbor tasks and dataset.toml."""
from __future__ import annotations

import argparse
from pathlib import Path
from .adapter import TwinEnvBenchAdapter


def write_dataset_toml(output_dir: Path, task_dirs: list[Path]) -> None:
    lines = [
        'schema_version = "1.0"',
        "",
        "[dataset]",
        'name = "tracelite-ai/twinenv-bench"',
        'version = "1.0.0"',
        'description = "TwinEnv-Bench: 117 counterfactual OS environment adaptation tasks (234 paired base/target cells)"',
        'authors = [{ name = "TraceLite AI", email = "contact@tracelite.ai" }]',
        "",
    ]
    for td in sorted(task_dirs):
        lines.extend([
            "[[tasks]]",
            f'path = "{td.name}"',
            "",
        ])
    (output_dir / "dataset.toml").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Harbor tasks for TwinEnv-Bench")
    parser.add_argument("--source-dir", type=Path, required=True, help="Path to TwinEnv-Bench repo/data directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for Harbor dataset")
    parser.add_argument("--tasks", nargs="+", help="Optional subset of canonical task IDs")
    parser.add_argument("--cells", default="base,target", help="Comma-separated cells (default: base,target)")
    args = parser.parse_args()

    adapter = TwinEnvBenchAdapter(source_dir=args.source_dir, output_dir=args.output_dir)
    cells = tuple(c.strip() for c in args.cells.split(",") if c.strip())
    generated = adapter.generate(task_ids=args.tasks, cells=cells)
    write_dataset_toml(args.output_dir, generated)
    print(f"Generated {len(generated)} Harbor tasks in {args.output_dir}")


if __name__ == "__main__":
    main()
