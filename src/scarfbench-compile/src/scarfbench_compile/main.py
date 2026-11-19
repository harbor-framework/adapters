from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scarfbench_compile.adapter import ScarfBenchCompileAdapter
else:
    from .adapter import ScarfBenchCompileAdapter


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

HARBOR_ROOT = Path(__file__).resolve().parents[4]
SCARFBENCH_REPO = "https://github.com/scarfbench/benchmark.git"

# Default output dir: <repo>/datasets/scarfbench-compile
DEFAULT_OUTPUT_DIR = HARBOR_ROOT / "datasets" / "scarfbench-compile"


def _clone_repo(dest: Path) -> None:
    logger.info("Cloning ScarfBench repository to %s ...", dest)
    subprocess.run(
        ["git", "clone", "--depth=1", SCARFBENCH_REPO, str(dest)],
        check=True,
    )
    logger.info("Clone complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert ScarfBench into Harbor task directories "
        "(compile + deploy + health, no smoke tests).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write generated tasks (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=None,
        help="Path to an already-cloned ScarfBench repo (skips git clone if provided)",
    )
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Generate only specific task IDs (e.g., cart-jakarta-to-quarkus)",
    )
    parser.add_argument(
        "--layer",
        type=str,
        default=None,
        help="Filter to a specific layer (e.g., business_domain, whole_applications)",
    )
    parser.add_argument(
        "--app",
        type=str,
        default=None,
        help="Filter to a specific application name (e.g., cart, cargotracker)",
    )
    parser.add_argument(
        "--from-framework",
        type=str,
        default=None,
        choices=["jakarta", "quarkus", "spring"],
        help="Filter to a specific source framework",
    )
    parser.add_argument(
        "--to-framework",
        type=str,
        default=None,
        choices=["jakarta", "quarkus", "spring"],
        help="Filter to a specific target framework",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Generate only the first N tasks (after filtering)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite task directories when they already exist",
    )
    parser.add_argument(
        "--docker-image",
        type=str,
        default=None,
        help="Pre-built toolchain image URL to embed in task.toml as "
        "docker_image = '...'.  Overrides SCARFBENCH_DOCKER_IMAGE env var.  "
        "Example: us-docker.pkg.dev/my-project/scarfbench/toolchain:latest",
    )

    parser.add_argument(
        "--task-image-repo",
        type=str,
        default=None,
        help="Per-task image repo.  task.toml gets docker_image = "
        "'<repo>:<task_id>', a thin image on top of --docker-image with the "
        "task's app/ baked in (build with docker/build-and-push-tasks.sh).  "
        "Required for hosts that skip environment/Dockerfile when docker_image "
        "is set.  Overrides SCARFBENCH_TASK_IMAGE_REPO.  "
        "Example: ghcr.io/scarfbench/scarfbench-tasks",
    )

    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Obtain the ScarfBench repo
    _temp_ctx: tempfile.TemporaryDirectory[str] | None = None
    if args.repo_dir:
        benchmark_dir = args.repo_dir
        if not benchmark_dir.exists():
            logger.error("--repo-dir does not exist: %s", benchmark_dir)
            sys.exit(1)
        logger.info("Using existing repo at %s", benchmark_dir)
    else:
        _temp_ctx = tempfile.TemporaryDirectory()
        benchmark_dir = Path(_temp_ctx.name) / "benchmark"
        try:
            _clone_repo(benchmark_dir)
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to clone ScarfBench repository: %s", exc)
            if _temp_ctx:
                _temp_ctx.cleanup()
            sys.exit(1)

    # docker_image: CLI flag > env var > None (omit from task.toml)
    docker_image: str | None = (
        args.docker_image or os.environ.get("SCARFBENCH_DOCKER_IMAGE") or None
    )
    if docker_image:
        logger.info("Using pre-built toolchain image: %s", docker_image)
    else:
        logger.warning(
            "No --docker-image / SCARFBENCH_DOCKER_IMAGE set.  "
            "Each task run will rebuild the toolchain image from scratch (~1–2 GB).  "
            "See src/scarfbench-compile/docker/README.md for the one-time build."
        )

    task_image_repo: str | None = (
        args.task_image_repo or os.environ.get("SCARFBENCH_TASK_IMAGE_REPO") or None
    )
    if docker_image and not task_image_repo:
        logger.warning(
            "--docker-image is set without --task-image-repo: hosts that skip "
            "environment/Dockerfile will give the agent an EMPTY /app."
        )

    try:
        adapter = ScarfBenchCompileAdapter(
            output_dir=output_dir,
            benchmark_dir=benchmark_dir,
            docker_image=docker_image,
            task_image_repo=task_image_repo,
        )

        task_ids = adapter.list_available_tasks()
        logger.info("Discovered %d tasks", len(task_ids))

        if args.layer or args.app or args.from_framework or args.to_framework:
            filtered = []
            for tid in task_ids:
                info = adapter.get_task_info(tid)
                if args.layer and info.get("layer") != args.layer:
                    continue
                if args.app and info.get("app_name") != args.app:
                    continue
                if (
                    args.from_framework
                    and info.get("framework_from") != args.from_framework
                ):
                    continue
                if args.to_framework and info.get("framework_to") != args.to_framework:
                    continue
                filtered.append(tid)
            task_ids = filtered

        if args.task_ids is not None:
            selected_ids = set(args.task_ids)
            task_ids = [tid for tid in task_ids if tid in selected_ids]
        if args.limit is not None:
            task_ids = task_ids[: args.limit]

        logger.info("Generating %d tasks into %s", len(task_ids), output_dir)
        ok = adapter.run(task_ids=task_ids, overwrite=args.overwrite)

        logger.info("Generated %d/%d tasks", ok, len(task_ids))
    finally:
        if _temp_ctx is not None:
            _temp_ctx.cleanup()


if __name__ == "__main__":
    main()
