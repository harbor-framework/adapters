"""Prepare checksum-pinned TextWorld archives for the adapter's --assets-dir.

Uses only Git and Python's standard library. Source checkouts are optional;
without them the two public upstream repositories are cloned at fixed commits.
Git archive reads committed bytes, preserving LF regardless of host settings.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


FIXTURES = Path(__file__).resolve().parents[1] / "src/balrog/fixtures"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(source: Path | None, *args: str) -> bytes:
    command = ["git", "-c", "core.autocrlf=false"]
    if source is not None:
        command += ["-C", str(source)]
    # Do not echo local Git configuration or credentials in diagnostics.
    result = subprocess.run(command + list(args), capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Git {args[0]} failed (exit {result.returncode}); check Git/network availability")
    return result.stdout


def checked_target(root: Path, relative: str) -> Path:
    part = PurePosixPath(relative)
    if part.is_absolute() or ".." in part.parts:
        raise ValueError(f"Unsafe archive destination: {relative}")
    target = root.joinpath(*part.parts)
    if not target.resolve().is_relative_to(root):
        raise ValueError(f"Archive destination escapes --assets-dir: {relative}")
    for candidate in (target, *target.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError(f"Archive destination contains a symlink: {relative}")
    return target


def source_checkout(root: Path, name: str, metadata: dict, supplied: Path | None) -> Path:
    commit = metadata["commit"]
    if supplied is not None:
        source = supplied.resolve(strict=True)
        if git(source, "rev-parse", "HEAD").decode().strip() != commit:
            raise ValueError(f"{name} source HEAD must equal pinned commit {commit}")
        return source
    source = checked_target(root, f".textworld-sources/{name}")
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        git(None, "clone", "--filter=blob:none", "--depth", "1", "--no-checkout", metadata["url"], str(source))
    if not (source / ".git").is_dir():
        raise ValueError(f"TextWorld source cache is not a Git repository: {source}")
    # The fixed public URL is used directly; no configured remote is trusted.
    git(source, "fetch", "--depth", "1", metadata["url"], commit)
    if git(source, "rev-parse", "FETCH_HEAD").decode().strip() != commit:
        raise ValueError(f"Fetched {name} source does not match the pinned commit")
    return source


def canonical_archive(source: Path, name: str, metadata: dict) -> bytes:
    raw = git(source, "archive", "--format=tar", metadata["commit"], *metadata["included_git_paths"])
    uncompressed = io.BytesIO()
    records = []
    excluded = set(metadata["excluded_path_components_case_insensitive"])
    allowed_suffixes = metadata["asset_suffix_allowlist"]
    with tarfile.open(fileobj=io.BytesIO(raw)) as original:
        with tarfile.open(fileobj=uncompressed, mode="w:") as target:
            for member in original:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("Unsafe path in upstream source archive")
                if any(part.lower() in excluded for part in path.parts):
                    continue
                if name == "assets":
                    if member.isdir() or path.suffix not in allowed_suffixes:
                        continue
                    member.name = path.relative_to("textworld").as_posix()
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"Unsupported source entry: {member.name}")
                content = original.extractfile(member).read() if member.isfile() else None
                if content is not None:
                    records.append({"path": member.name, "sha256": sha256(content), "bytes": len(content)})
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mtime = 0
                member.pax_headers = {}
                target.addfile(member, io.BytesIO(content) if content is not None else None)
    expected_files = [{key: item[key] for key in ("path", "sha256", "bytes")} for item in metadata["files"]]
    if records != expected_files:
        raise ValueError(f"{name} committed files differ from the frozen source manifest")
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0) as stream:
        stream.write(uncompressed.getvalue())
    data = compressed.getvalue()
    if sha256(data) != metadata["archive_sha256"]:
        raise ValueError(f"Canonical {name} archive differs from its frozen checksum")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, required=True, help="Output directory passed unchanged to balrog --assets-dir")
    parser.add_argument("--textworld-source", type=Path, help="Optional existing TextWorld checkout at the pinned HEAD")
    parser.add_argument("--games-source", type=Path, help="Optional existing intelligent-go-explore checkout at the pinned HEAD")
    parser.add_argument("--check-only", action="store_true", help="Validate existing archives without network or writes")
    args = parser.parse_args(argv)
    metadata = json.loads((FIXTURES / "textworld_sources.json").read_text(encoding="utf-8"))
    runtime = json.loads((FIXTURES / "runtime_sources.json").read_text(encoding="utf-8"))["textworld"]
    expected = {item["archive"]: item for item in runtime}
    root = args.assets_dir.resolve()
    records = []
    for name, source in (("textworld", args.textworld_source), ("assets", args.games_source)):
        item = expected[f"{name}.tar.gz"]
        if item["commit"] != metadata[name]["commit"] or item["sha256"] != metadata[name]["archive_sha256"]:
            raise ValueError("Runtime and TextWorld source pins disagree")
        destination = checked_target(root, item["path"])
        if destination.exists():
            if not destination.is_file() or sha256(destination.read_bytes()) != item["sha256"]:
                raise ValueError(f"Existing archive fails its pinned checksum: {destination}")
            status = "verified"
        elif args.check_only:
            raise FileNotFoundError(f"Missing pinned archive: {destination}")
        else:
            checkout = source_checkout(root, name, metadata[name], source)
            data = canonical_archive(checkout, name, metadata[name])
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Refuse to overwrite a file created concurrently after our check.
            with destination.open("xb") as stream:
                stream.write(data)
            status = "prepared"
        records.append({"archive": item["path"], "commit": item["commit"], "sha256": item["sha256"], "status": status})
    print(json.dumps({"assets_dir": str(root), "archives": records}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"TextWorld asset preparation failed: {exc}") from None
