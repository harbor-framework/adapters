"""Write the original-side dataset dir for parity: exactly the challenges the adapter
ships (those in oracle_solutions.json), in the layout `vimgolf-benchmark.py
--dataset-format vimgolf_public --dataset-dir` reads (<challenge id>/challenge.json,
metadata.json). The id list is written to <out dir>.ids.json.

Usage: python parity/make_subset_dir.py <challenges.zip> <out dir>
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vimgolf_gym.adapter import HF_ZIP_SHA256, load_oracles  # noqa: E402


def main() -> None:
    zip_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    data = zip_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != HF_ZIP_SHA256:
        raise ValueError(f"{zip_path}: sha256 does not match the pinned challenges.zip")
    ids = sorted(load_oracles())
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty: vimgolf-benchmark.py runs every entry in it")
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for cid in ids:
            (out / cid).mkdir(exist_ok=True)
            for name in ("challenge.json", "metadata.json"):
                (out / cid / name).write_bytes(zf.read(f"challenges/{cid}/{name}"))
    # next to the dir, not in it: vimgolf-benchmark.py treats every entry as a task
    out.with_name(out.name + ".ids.json").write_text(json.dumps(ids, indent=1) + "\n")
    print(f"{len(ids)} challenges -> {out}")


if __name__ == "__main__":
    main()
