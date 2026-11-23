"""Prepare the pinned Baba runtime archive, without model calls or credentials."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

COMMIT = "40ae1b29dbc67f2ecea06cc161ed5ca51719e5e3"
URL = "https://github.com/nacloos/baba-is-ai.git"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    lock = json.loads((project / "src/balrog/fixtures/runtime_sources.json").read_text())["babaisai"][0]
    destination = args.assets_dir / lock["path"]
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != lock["sha256"]:
            raise ValueError("Existing archive differs from the pinned hash; choose a clean assets directory")
        print(f"Verified {destination}")
        return
    if args.check_only:
        raise FileNotFoundError(destination)
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="baba-source-", dir=args.assets_dir) as work:
        source = args.source
        if source is None:
            source = Path(work) / "source"
            subprocess.run(["git", "clone", "--no-checkout", URL, str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "checkout", "--detach", COMMIT], check=True)
        actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != COMMIT:
            raise ValueError("Source checkout is not at the pinned Baba commit")
        raw = subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(source), "archive",
                                       "--format=tar", COMMIT, "baba", "setup.py", "README.md", "LICENSE"])
        content = bytearray(gzip.compress(raw, compresslevel=9, mtime=0))
        # Preserve the frozen archive's canonical gzip OS header on every host.
        content[9] = 10
        if hashlib.sha256(content).hexdigest() != lock["sha256"]:
            raise ValueError("Rebuilt archive differs from the frozen artifact; nothing was overwritten")
        with destination.open("xb") as output:
            output.write(content)
    print(f"Prepared {destination}")


if __name__ == "__main__":
    main()
