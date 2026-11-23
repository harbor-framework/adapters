"""Fail builds on source, package, or OS drift; never resolve dependencies."""
import argparse
import base64
import csv
import hashlib
import importlib.metadata as metadata
import io
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(lock, directory):
    if sys.platform != "linux" or platform.machine() != "x86_64" or sys.implementation.name != "cpython":
        raise ValueError("BALROG runtime locks require CPython on Linux x86_64")
    for name in ("requirements-game.lock", "apt-game.lock"):
        if sha256(directory / name) != lock[name + "_sha256"]:
            raise ValueError(f"Runtime dependency lock changed: {name}")


def install_python(lock, directory):
    verify_inputs(lock, directory)
    lines = [line for line in (directory / "requirements-game.lock").read_text().splitlines()
             if line and not line.startswith("#")]
    # Install locked wheels first so sdist builds can use the pinned numpy/cffi
    # and packaging tools. No PEP 517 build environment may fetch newer tools.
    for kind, selected in (("wheels", [line for line in lines if ".whl " in line]),
                           ("sdists", [line for line in lines if ".whl " not in line])):
        if selected:
            requirements = directory / f"requirements-{kind}.lock"
            requirements.write_text("\n".join(selected) + "\n")
            subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--no-deps",
                            "--no-build-isolation", "--require-hashes", "-r", str(requirements)], check=True)


def verify_sources(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    entries = manifest.get("archives") or {
        value["archive"]: value for value in manifest.values() if isinstance(value, dict) and "archive" in value}
    if not entries or {p.name for p in directory.glob("*.tar.gz")} != set(entries):
        raise ValueError("Source archives do not match vendor manifest")
    for name, entry in entries.items():
        if Path(name).name != name or sha256(directory / name) != entry["sha256"]:
            raise ValueError(f"Pinned source archive changed: {name}")
    return entries


def install_apt(lock, directory):
    verify_inputs(lock, directory)
    additions = [line for line in (directory / "apt-game.lock").read_text().splitlines()
                 if line and not line.startswith("#")]
    if not additions:
        return
    snapshot = lock["apt_snapshot"]
    if not re.fullmatch(r"\d{8}T\d{6}Z", snapshot):
        raise ValueError("Invalid Debian snapshot timestamp")
    # The snapshot retains exact binary packages after normal mirrors rotate.
    sources = Path("/etc/apt/sources.list.d/debian.sources")
    sources.write_text(
        f"Types: deb\nURIs: https://snapshot.debian.org/archive/debian/{snapshot}/\n"
        "Suites: bookworm bookworm-updates\nComponents: main\n"
        "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\nCheck-Valid-Until: no\n\n"
        f"Types: deb\nURIs: https://snapshot.debian.org/archive/debian-security/{snapshot}/\n"
        "Suites: bookworm-security\nComponents: main\n"
        "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\nCheck-Valid-Until: no\n")
    subprocess.run(["apt-get", "update"], check=True)
    subprocess.run(["apt-get", "install", "-y", "--no-install-recommends", *additions], check=True)


def distribution_file_hashes(name):
    dist = metadata.distribution(name)
    return {str(path): sha256(dist.locate_file(path)) for path in dist.files or []
            if dist.locate_file(path).is_file()}


def patch_baba(lock, directory):
    patch = lock["metadata_patch"]
    dist = metadata.distribution(patch["distribution"])
    if dist.version != patch["version"]:
        raise ValueError("Unexpected Baba source distribution version")
    before = distribution_file_hashes("opencv-python-headless")
    metadata_file = next(p for p in dist.files if str(p).endswith(".dist-info/METADATA"))
    path = Path(dist.locate_file(metadata_file))
    lines = path.read_text().splitlines(keepends=True)
    if sum(line.rstrip("\r\n") == patch["old"] for line in lines) != 1:
        raise ValueError("Baba dependency metadata differs from the reviewed patch")
    path.write_text("".join(patch["new"] + "\n" if line.rstrip("\r\n") == patch["old"] else line
                            for line in lines))
    # Keep wheel RECORD accurate after the explicitly recorded metadata-only fix.
    record_file = next(p for p in dist.files if str(p).endswith(".dist-info/RECORD"))
    record_path = Path(dist.locate_file(record_file))
    rows = list(csv.reader(io.StringIO(record_path.read_text())))
    digest = base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).rstrip(b"=").decode()
    for row in rows:
        if row[0] == str(metadata_file):
            row[1:] = ["sha256=" + digest, str(path.stat().st_size)]
    with record_path.open("w", newline="") as stream:
        csv.writer(stream).writerows(rows)
    after = distribution_file_hashes("opencv-python-headless")
    if before != after:
        raise ValueError("OpenCV binaries changed during metadata correction")
    (directory / "metadata-patch.json").write_text(json.dumps(
        {**patch, "opencv_files_unchanged": True, "opencv_file_sha256": after}, indent=2) + "\n")


def verify(lock, directory):
    verify_inputs(lock, directory)
    if sys.version != lock["python"]:
        raise ValueError("Python version/build differs from the pinned base")
    actual = {canonical(dist.metadata["Name"]): dist.version for dist in metadata.distributions()}
    if actual != lock["packages"]:
        missing = {k: v for k, v in lock["packages"].items() if actual.get(k) != v}
        extra = {k: v for k, v in actual.items() if lock["packages"].get(k) != v}
        raise ValueError(f"Python runtime drift: expected={missing}, actual={extra}")
    output = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"], text=True)
    apt = {name: {"version": version, "architecture": arch}
           for name, version, arch in (line.split("\t") for line in output.splitlines())}
    if apt != lock["apt"]:
        changed = {k: v for k, v in apt.items() if lock["apt"].get(k) != v}
        missing = {k: v for k, v in lock["apt"].items() if apt.get(k) != v}
        raise ValueError(f"OS runtime drift: expected={missing}, actual={changed}")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    (directory / "runtime-validation.json").write_text(json.dumps(
        {"environment": lock["environment"], "python": sys.version, "packages": actual,
         "apt": apt, "pip_check": "passed", "runtime_lock_sha256": sha256(directory / "runtime-lock.json")},
        indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apt", "python", "sources", "patch-baba", "verify"))
    parser.add_argument("--directory", type=Path, default=Path("/opt"))
    parser.add_argument("--vendor", type=Path, default=Path("/tmp/vendor"))
    args = parser.parse_args()
    lock = json.loads((args.directory / "runtime-lock.json").read_text())
    if args.action == "sources":
        verify_sources(args.vendor)
    elif args.action == "apt":
        install_apt(lock, args.directory)
    elif args.action == "python":
        install_python(lock, args.directory)
    elif args.action == "patch-baba":
        patch_baba(lock, args.directory)
    else:
        verify(lock, args.directory)
