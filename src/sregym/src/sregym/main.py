"""CLI entry point: generate Harbor tasks from SREGym.

    uv run sregym                                  # SREGym-Lite (17) -> datasets/sregym-lite
    uv run sregym --split full                     # full SREGym       -> datasets/sregym
    uv run sregym --task-ids network_policy_block --overwrite --output-dir /tmp/t

The default uses the bundled metadata snapshot for the pinned SREGym commit.
To re-extract from a checkout (for example a newer SREGym), pass
``--sregym-root``, or ``--clone`` to clone it to a temporary directory. The
extractor runs with SREGym's own environment (``uv run`` in that checkout).
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from .adapter import (
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_SIDECAR_IMAGE,
    PACKAGE_DIR,
    SPLITS,
    SREGYM_COMMIT,
    SREGYM_REPO,
    SregymAdapter,
    Timeouts,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sregym.main")


def extract_metadata(sregym_root: Path, out: Path) -> Path:
    script = PACKAGE_DIR / "extract_metadata.py"
    subprocess.run(
        ["uv", "run", "--frozen", "python", str(script), "--out", str(out)],
        cwd=sregym_root,
        check=True,
    )
    return out


def clone_sregym(dest: Path, commit: str) -> Path:
    subprocess.run(["git", "clone", "--recurse-submodules", SREGYM_REPO, str(dest)], check=True)
    subprocess.run(["git", "checkout", commit], cwd=dest, check=True)
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=dest, check=True)
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output-dir", type=Path, default=None, help="Default: datasets/sregym-lite for --split lite, else datasets/sregym")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--task-ids", nargs="+", default=None, help="SREGym problem IDs (or sanitized task names)")
    p.add_argument("--split", choices=list(SPLITS), default="lite")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--metadata", type=Path, help="Pre-extracted problems_metadata.json")
    src.add_argument("--sregym-root", type=Path, help="Existing SREGym checkout to extract from")
    src.add_argument("--clone", action="store_true", help=f"Clone SREGym @ {SREGYM_COMMIT} and extract")
    p.add_argument("--sidecar-image", default=DEFAULT_SIDECAR_IMAGE)
    p.add_argument("--sidecar-pull-policy", default="never", choices=["never", "missing", "always"])
    p.add_argument(
        "--sidecar-cpus", type=int, default=None, help="Override sidecar CPUs (default: 8, or 16 for large apps)"
    )
    p.add_argument(
        "--sidecar-memory", default=None, help="Override sidecar memory (default: 16g, or 32g for large apps)"
    )
    p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL, help="Default LLM judge for diagnosis (override at run time with SREGYM_JUDGE_MODEL)")
    p.add_argument(
        "--oracle-secret",
        default=os.environ.get("SREGYM_ORACLE_SECRET"),
        help="Private secret for per-task oracle tokens (default: random per generation; env SREGYM_ORACLE_SECRET)",
    )
    p.add_argument("--network", choices=["allowlist", "public"], default="allowlist",
                   help="Agent-phase egress (default: allowlist, like upstream's filtered mode)")
    p.add_argument("--allow-host", action="append", default=[],
                   help="Extra allowlisted host for the agent phase (repeatable)")
    p.add_argument("--agent-timeout", type=int, default=Timeouts.agent_sec)
    p.add_argument("--build-timeout", type=int, default=Timeouts.build_sec)
    p.add_argument("--verifier-timeout", type=int, default=Timeouts.verifier_sec)
    args = p.parse_args()

    if args.output_dir is None:
        args.output_dir = Path("datasets/sregym-lite" if args.split == "lite" else f"datasets/sregym{'' if args.split == 'full' else '-' + args.split}")
    metadata = args.metadata
    with tempfile.TemporaryDirectory() as tmp:
        if args.clone:
            root = clone_sregym(Path(tmp) / "SREGym", SREGYM_COMMIT)
            metadata = extract_metadata(root, Path(tmp) / "problems_metadata.json")
        elif args.sregym_root:
            metadata = extract_metadata(args.sregym_root.resolve(), Path(tmp) / "problems_metadata.json")

        adapter = SregymAdapter(
            args.output_dir,
            limit=args.limit,
            overwrite=args.overwrite,
            task_ids=args.task_ids,
            split=args.split,
            metadata_path=metadata,
            sidecar_image=args.sidecar_image,
            sidecar_pull_policy=args.sidecar_pull_policy,
            sidecar_cpus=args.sidecar_cpus,
            sidecar_memory=args.sidecar_memory,
            judge_model=args.judge_model,
            oracle_secret=args.oracle_secret,
            network=args.network,
            allowed_hosts=(*DEFAULT_ALLOWED_HOSTS, *args.allow_host),
            timeouts=Timeouts(args.agent_timeout, args.build_timeout, args.verifier_timeout),
        )
        adapter.run()


if __name__ == "__main__":
    main()
