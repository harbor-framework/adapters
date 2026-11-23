"""Hand the agent's work from its sandbox to the verifier's. See collect.sh and test.sh.

pack runs as root in the agent's sandbox after the agent's processes are gone. It writes one tar
stream, with the agent's home under home/ and the /tmp targets of the task directory's links
under tmp/, in parts of at most PART_BYTES, and manifest.json with each part's size and checksum.
task.toml declares every part as an artifact, so Harbor downloads each one on its own and no
single transfer is larger than a part. The stream leaves out the model files that the
healthcheck downloaded and that are still unchanged, because the verifier downloads the same
revision; a hard link to such a file or a copy of it elsewhere is recorded in the manifest
instead of its content. It also leaves out the xet client's download cache. Symbolic links are
kept as they are, hard links within the home or within the /tmp targets stay hard links (a /tmp
file that is linked to a file in the home gets a copy of its own), and sockets, pipes, and device
files are left out. Each part starts with a header that holds a NUL
byte, so that Harbor's secret scrubbing, which rewrites text files, leaves every part as it is.

verify runs as root in the verifier's sandbox and checks the parts against the manifest.

stream runs as root there and writes the parts to stdout, checking them again.

unpack runs as user agent there and needs no access to the hand-off: it reads the stream on
stdin and the manifest from an inherited file descriptor. It extracts the stream, puts the model
files back from a fresh download of the same revision, and only then gives the directories their
modes. A member that would leave its destination, pass through a symbolic link, or link to
anything but a file of the stream is refused, and no file keeps a set-user-ID, set-group-ID, or
sticky bit.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

MANIFEST = "manifest.json"
PART = "part.{:03d}"
PART_HEADER_BYTES = 512
# Harbor cannot download a file above 5 GiB from Modal (harbor-framework/harbor#3924).
PART_BYTES = 2 << 30
# task.toml declares this many parts (adapter.HANDOFF_PARTS), so the hand-off holds up to 80 GiB.
MAX_PARTS = 40
HOME, TMP = "home", "tmp"
# The xet client's chunk cache. Nothing reads it after a download, and it can hold gigabytes.
XET_CACHE = "hf_cache/xet"
HUB = "hf_cache/hub"
# The Hub names a file after its sha256 if it is stored in LFS, and after its git blob hash if not.
BLOB = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# A file this large that has the size of an unchanged model file is hashed to find copies of it.
MIN_COPY_BYTES = 1 << 20
CHUNK = 16 << 20
HASH_THREADS = 8
# The healthcheck writes the start of the agent's budget here, as root.
TIMER = Path("/timer_start")
NVIDIA_SMI = ("/usr/bin/nvidia-smi", "/usr/local/nvidia/bin/nvidia-smi")
GPU_FIELDS = ("name", "memory_total_mib", "driver_version")
PROVIDER_ENV = ("MODAL_CLOUD_PROVIDER", "MODAL_REGION", "MODAL_IMAGE_ID", "MODAL_TASK_ID", "DAYTONA_SANDBOX_ID")


def part_header(index: int) -> bytes:
    return f"InferenceBench hand-off part {index:03d}\n".encode().ljust(PART_HEADER_BYTES, b"\0")


def log(message: str) -> None:
    print(f"[handoff] {message}", flush=True)


def safe_relative(name: str) -> tuple[str, ...] | None:
    """Return the components of a relative path that stays below its root, else None."""
    if not name or name.startswith("/"):
        return None
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts:
        return None
    return parts


def open_beneath(root: str, relative: str, flags: int) -> int:
    """Open root/relative without following a symbolic link in any component."""
    parts = safe_relative(relative)
    if parts is None:
        raise OSError(f"not a relative path: {relative!r}")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=fd)
    finally:
        os.close(fd)


def digest_of(fd: int, name: str, size: int) -> str:
    """The id that the Hub would give this content: sha256, or the git blob hash for a short name."""
    digest = hashlib.sha256() if len(name) == 64 else hashlib.sha1(b"blob %d\0" % size)
    with os.fdopen(os.dup(fd), "rb", buffering=0) as stream:
        stream.seek(0)
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def intact_blobs(root: str, repository: str, blobs: list[dict]) -> list[dict]:
    """The blobs under root/repository/blobs that still have the recorded content.

    Each result also has the file's mode, modification time, and inode."""

    def check(blob: dict) -> dict | None:
        name, size = blob.get("name"), blob.get("size")
        if not isinstance(name, str) or not BLOB.fullmatch(name) or not isinstance(size, int):
            return None
        try:
            fd = open_beneath(root, f"{repository}/blobs/{name}", os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            return None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size != size or digest_of(fd, name, size) != name:
                return None
            return {
                "name": name,
                "size": size,
                "mode": stat.S_IMODE(info.st_mode) & 0o777,
                "mtime": int(info.st_mtime),
                "inode": (info.st_dev, info.st_ino),
            }
        finally:
            os.close(fd)

    with ThreadPoolExecutor(max_workers=HASH_THREADS) as pool:
        return [blob for blob in pool.map(check, blobs) if blob is not None]


class PartWriter:
    """A write-only file object that splits what passes through it into numbered parts."""

    def __init__(self, directory: Path, part_bytes: int, max_parts: int):
        self.directory, self.part_bytes, self.max_parts = directory, part_bytes, max_parts
        self.parts: list[dict] = []
        self.current = None
        self.size = 0

    def _close_part(self) -> None:
        if self.current is None:
            return
        stream, name, digest, size = self.current
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        (self.directory / name).chmod(0o644)
        self.parts.append({"name": name, "bytes": PART_HEADER_BYTES + size, "sha256": digest.hexdigest()})
        self.current = None

    def _next_part(self) -> None:
        self._close_part()
        if len(self.parts) >= self.max_parts:
            raise SystemExit(
                f"the hand-off is larger than {self.max_parts} parts of {self.part_bytes} bytes, "
                "which is all that task.toml declares"
            )
        name = PART.format(len(self.parts))
        # A part stays open across writes, until it is full or the stream ends.
        self.current = [open(self.directory / name, "xb"), name, hashlib.sha256(), 0]  # noqa: SIM115
        header = part_header(len(self.parts))
        self.current[0].write(header)
        self.current[2].update(header)

    def write(self, data) -> int:
        view = memoryview(data).cast("B")
        self.size += len(view)
        while view:
            if self.current is None or self.current[3] == self.part_bytes:
                self._next_part()
            piece = view[: self.part_bytes - self.current[3]]
            self.current[0].write(piece)
            self.current[2].update(piece)
            self.current[3] += len(piece)
            view = view[len(piece) :]
        return len(data)

    def flush(self) -> None:
        if self.current is not None:
            self.current[0].flush()

    def close(self) -> None:
        self._close_part()


class Packer:
    """Add trees to a tar stream without following symbolic links."""

    def __init__(self, tar: tarfile.TarFile, leave_out: set[str], left_out: list[dict]):
        self.tar = tar
        self.leave_out = leave_out
        self.by_inode = {blob["inode"]: blob["name"] for blob in left_out}
        self.by_size: dict[int, set[str]] = {}
        for blob in left_out:
            if len(blob["name"]) == 64 and blob["size"] >= MIN_COPY_BYTES:
                self.by_size.setdefault(blob["size"], set()).add(blob["name"])
        self.model_files: list[dict] = []
        self.counts: Counter[str] = Counter()
        self.bytes = 0

    def add_tree(self, path: str, arcname: str) -> None:
        stack = [(path, arcname)]
        while stack:
            path, arcname = stack.pop()
            if arcname in self.leave_out:
                self.counts["left out on purpose"] += 1
                continue
            info = os.lstat(path)
            if stat.S_ISDIR(info.st_mode):
                self.tar.addfile(self.tar.gettarinfo(path, arcname))
                self.counts["directories"] += 1
                with os.scandir(path) as entries:
                    names = sorted((entry.name for entry in entries), reverse=True)
                stack.extend((os.path.join(path, name), f"{arcname}/{name}") for name in names)
            elif stat.S_ISREG(info.st_mode):
                self.add_file(path, arcname)
            elif stat.S_ISLNK(info.st_mode):
                self.tar.addfile(self.tar.gettarinfo(path, arcname))
                self.counts["symbolic links"] += 1
            else:
                self.counts["special files left out"] += 1
                log(f"left out {path}: not a file, a directory, or a symbolic link")

    def add_file(self, path: str, arcname: str) -> None:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                self.counts["special files left out"] += 1
                log(f"left out {path}: it changed while it was packed")
                return
            blob, kind = self.by_inode.get((info.st_dev, info.st_ino)), "link"
            if blob is None and info.st_size in self.by_size:
                digest = digest_of(stream.fileno(), "0" * 64, info.st_size)
                blob, kind = (digest, "copy") if digest in self.by_size[info.st_size] else (None, None)
            if blob is not None:
                self.model_files.append(
                    {
                        "path": arcname,
                        "blob": blob,
                        "kind": kind,
                        "mode": stat.S_IMODE(info.st_mode) & 0o777,
                        "mtime": int(info.st_mtime),
                    }
                )
                self.counts[f"model file {kind}s"] += 1
                return
            stream.seek(0)
            member = self.tar.gettarinfo(arcname=arcname, fileobj=stream)
            if member.islnk():
                self.tar.addfile(member)
                self.counts["hard links"] += 1
                return
            self.tar.addfile(member, stream)
        self.counts["files"] += 1
        self.bytes += member.size
        if member.size > 2 * info.st_blocks * 512 + (64 << 20):
            log(f"{path} is sparse: {member.size} bytes are stored for {info.st_blocks * 512} on disk")


def outermost(targets: list[str]) -> list[str]:
    """Drop the targets that another target contains, so that no path is archived twice."""
    kept: list[str] = []
    for target in sorted({os.path.normpath(target) for target in targets}, key=lambda t: (t.count("/"), t)):
        if not any(target == other or target.startswith(other + "/") for other in kept):
            kept.append(target)
    return sorted(kept)


def agent_sandbox() -> dict:
    """What the agent ran on, for the record; the verifier runs on another sandbox."""
    found = {"provider": {name: os.environ[name] for name in PROVIDER_ENV if name in os.environ}}
    for path in NVIDIA_SMI:
        if os.path.isfile(path):
            try:
                rows = subprocess.run(
                    [path, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=60, check=True,
                ).stdout
                found["gpus"] = [dict(zip(GPU_FIELDS, row.split(", "))) for row in rows.splitlines() if row.strip()]
            except (OSError, subprocess.SubprocessError):
                pass
            break
    return found


def pack(args: argparse.Namespace) -> None:
    home, out = str(args.home), args.out
    leave_out = {f"{HOME}/{XET_CACHE}"}
    model, left_out = None, []
    if args.record.is_file():
        record = json.loads(args.record.read_text(encoding="utf-8"))
        repository = record["repository"]
        if safe_relative(repository) is None or not repository.startswith(f"{HUB}/models--"):
            raise SystemExit(f"the healthcheck's record names an unexpected repository: {repository!r}")
        left_out = intact_blobs(home, repository, record["blobs"])
        leave_out |= {f"{HOME}/{repository}/blobs/{blob['name']}" for blob in left_out}
        model = {
            "repository": repository,
            "revision": record["revision"],
            "left_out": [{key: blob[key] for key in ("name", "size", "mode", "mtime")} for blob in left_out],
            "changed": sorted({blob["name"] for blob in record["blobs"]} - {blob["name"] for blob in left_out}),
        }
        log(
            f"{len(left_out)} of {len(record['blobs'])} downloaded model files are unchanged "
            f"({sum(blob['size'] for blob in left_out)} bytes) and stay out of the stream"
        )
    else:
        log(f"no record of the model download at {args.record}; every file is packed")
    targets = outermost([os.fsdecode(target) for target in args.tmp_list.read_bytes().split(b"\0") if target])
    writer = PartWriter(out, args.part_bytes, MAX_PARTS)
    with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        packer = Packer(tar, leave_out, left_out)
        packer.add_tree(home, HOME)
        # A /tmp target that shares a file with the home gets its own copy, as with cp -a.
        tar.inodes.clear()
        for target in targets:
            packer.add_tree(target, f"{TMP}/{target[len('/tmp/'):]}")
    writer.close()
    if model is not None:
        model["files"] = packer.model_files
    try:
        budget_started = int(TIMER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        budget_started = None
    manifest = {
        "format": 2,
        "packed_at_unix": int(time.time()),
        "budget_started_at_unix": budget_started,
        "agent_sandbox": agent_sandbox(),
        "parts": writer.parts,
        "stream_bytes": writer.size,
        "left_out": [XET_CACHE],
        "model": model,
        "tmp_targets": targets,
        "entries": dict(packer.counts),
        "file_bytes": packer.bytes,
    }
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / MANIFEST).chmod(0o644)
    log(f"{writer.size} bytes in {len(writer.parts)} parts: {dict(packer.counts)}")


def read_manifest(stream) -> dict:
    manifest = json.load(stream)
    if manifest.get("format") != 2:
        raise ValueError(f"unknown hand-off format {manifest.get('format')!r}")
    return manifest


def check_manifest(manifest: dict, model_id: str, revision: str) -> None:
    parts = manifest["parts"]
    if not 1 <= len(parts) <= MAX_PARTS or [part["name"] for part in parts] != [
        PART.format(index) for index in range(len(parts))
    ]:
        raise ValueError(f"unexpected parts: {[part.get('name') for part in parts]}")
    model = manifest["model"]
    if model is None:
        return
    repository = f"{HUB}/models--{model_id.replace('/', '--')}"
    if model["repository"] != repository or model["revision"] != revision:
        raise ValueError(f"the hand-off is for {model['repository']} at {model['revision']}")
    names = set()
    for blob in model["left_out"]:
        if not BLOB.fullmatch(str(blob.get("name"))) or not all(
            isinstance(blob.get(key), int) for key in ("size", "mode", "mtime")
        ):
            raise ValueError(f"not a model file: {blob!r}")
        names.add(blob["name"])
    for entry in model.get("files", []):
        parts_of = safe_relative(str(entry.get("path")))
        if (
            parts_of is None
            or len(parts_of) < 2
            or parts_of[0] not in (HOME, TMP)
            or entry.get("blob") not in names
            or entry.get("kind") not in ("link", "copy")
            or not isinstance(entry.get("mode"), int)
            or not isinstance(entry.get("mtime"), int)
        ):
            raise ValueError(f"not a copy of a model file: {entry!r}")


def part_digest(path: Path) -> tuple[int, str]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb", buffering=0) as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def verify(args: argparse.Namespace) -> None:
    try:
        with open(args.handoff / MANIFEST, "rb") as stream:
            manifest = read_manifest(stream)
        check_manifest(manifest, args.model, args.revision)
        for index, part in enumerate(manifest["parts"]):
            with open(args.handoff / part["name"], "rb") as stream:
                if stream.read(PART_HEADER_BYTES) != part_header(index):
                    raise ValueError(f"{part['name']} does not start with the header of part {index}")
            found = part_digest(args.handoff / part["name"])
            if found != (part["bytes"], part["sha256"]):
                raise ValueError(f"{part['name']}: {found[0]} bytes with sha256 {found[1]}, expected {part}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"the hand-off is incomplete or damaged: {error}") from error
    log(f"the hand-off packed at {manifest['packed_at_unix']} is complete: {len(manifest['parts'])} parts")


def stream_parts(args: argparse.Namespace) -> None:
    with open(args.handoff / MANIFEST, "rb") as stream:
        manifest = read_manifest(stream)
    out = sys.stdout.buffer
    for index, part in enumerate(manifest["parts"]):
        digest, size = hashlib.sha256(), 0
        with open(args.handoff / part["name"], "rb", buffering=0) as stream:
            header = stream.read(PART_HEADER_BYTES)
            if header != part_header(index):
                raise SystemExit(f"{part['name']} does not start with the header of part {index}")
            digest.update(header)
            size += len(header)
            while chunk := stream.read(CHUNK):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
        if (size, digest.hexdigest()) != (part["bytes"], part["sha256"]):
            raise SystemExit(f"{part['name']} changed after it was checked")
    out.flush()


class Extractor:
    """Extract a tar stream into one directory per top-level name, refusing what could leave them."""

    def __init__(self, destinations: dict[str, Path]):
        self.destinations = destinations
        self.counts: Counter[str] = Counter()
        self.directories: list[tuple[Path, int, float]] = []
        self.checked: set[tuple[str, tuple[str, ...]]] = set()
        self.files: set[tuple[str, tuple[str, ...]]] = set()
        # The stream comes from pack, not from the agent; the checks below are what matters.
        self.trusted = {"filter": "fully_trusted"} if hasattr(tarfile, "fully_trusted_filter") else {}

    def locate(self, name: str) -> tuple[str, tuple[str, ...]] | None:
        parts = safe_relative(name)
        if parts is None or parts[0] not in self.destinations:
            return None
        return parts[0], parts[1:]

    def real_directories(self, top: str, parts: tuple[str, ...]) -> bool:
        """Whether every existing component of parts below top's destination is a real directory."""
        for depth in range(1, len(parts) + 1):
            prefix = parts[:depth]
            if (top, prefix) in self.checked:
                continue
            path = self.destinations[top].joinpath(*prefix)
            if os.path.lexists(path):
                if path.is_symlink() or not path.is_dir():
                    return False
                self.checked.add((top, prefix))
        return True

    def refuse(self, member: tarfile.TarInfo, reason: str) -> None:
        self.counts["refused"] += 1
        log(f"refused {member.name!r}: {reason}")

    def extract(self, stream) -> None:
        with tarfile.open(fileobj=stream, mode="r|") as tar:
            for member in tar:
                located = self.locate(member.name)
                if located is None:
                    self.refuse(member, "the path leaves the destination")
                    continue
                top, parts = located
                destination = self.destinations[top]
                member.mode &= 0o777
                if not parts:
                    if member.isdir():
                        self.directories.append((destination, member.mode, member.mtime))
                    else:
                        self.refuse(member, "not a directory")
                    continue
                if not (member.isreg() or member.isdir() or member.issym() or member.islnk()):
                    self.refuse(member, "not a file, a directory, or a link")
                    continue
                if not self.real_directories(top, parts[:-1]):
                    self.refuse(member, "a parent directory is a symbolic link or a file")
                    continue
                target = destination.joinpath(*parts)
                if os.path.lexists(target):
                    self.refuse(member, "the path exists already")
                    continue
                member.name = "/".join(parts)
                if member.islnk():
                    link = self.locate(member.linkname)
                    if link is None or link[0] != top or (top, link[1]) not in self.files:
                        self.refuse(member, "a hard link must point to a file of the stream")
                        continue
                    member.linkname = "/".join(link[1])
                if member.isdir():
                    # A directory gets its mode in finish, so that a read-only one can be filled.
                    self.directories.append((target, member.mode, member.mtime))
                    tar.extract(member, destination, set_attrs=False, **self.trusted)
                    self.counts["directories"] += 1
                    continue
                tar.extract(member, destination, set_attrs=True, **self.trusted)
                if member.isreg():
                    self.files.add((top, parts))
                kind = "symbolic links" if member.issym() else "hard links" if member.islnk() else "files"
                self.counts[kind] += 1

    def finish(self) -> None:
        for target, mode, mtime in sorted(self.directories, key=lambda entry: len(entry[0].parts), reverse=True):
            os.chmod(target, mode)
            os.utime(target, (mtime, mtime))


def place_model_files(manifest: dict, extractor: Extractor, staging: Path) -> int:
    """Put the model files that pack left out back, from the staging cache of a fresh download."""
    model = manifest["model"]
    if model is None:
        return 0
    repository = model["repository"]
    source_repository = repository[len(HUB) + 1 :]
    intact = {blob["name"]: blob for blob in intact_blobs(str(staging), source_repository, model["left_out"])}
    missing = sorted({blob["name"] for blob in model["left_out"]} - set(intact))
    if missing:
        raise SystemExit(f"the fresh download does not have these model files: {missing}")
    home = extractor.destinations[HOME]
    blobs_dir = PurePosixPath(repository, "blobs").parts
    if model["left_out"] and not (extractor.real_directories(HOME, blobs_dir) and home.joinpath(*blobs_dir).is_dir()):
        raise SystemExit(f"{home.joinpath(*blobs_dir)} is not a directory in the agent's home")
    for blob in model["left_out"]:
        source = staging / source_repository / "blobs" / blob["name"]
        target = home.joinpath(*blobs_dir, blob["name"])
        if os.path.lexists(target):
            raise SystemExit(f"{target} exists, although the hand-off left it out")
        try:
            os.rename(source, target)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            shutil.copyfile(source, target)
        os.chmod(target, blob["mode"])
        os.utime(target, (blob["mtime"], blob["mtime"]))
    for entry in model.get("files", []):
        top, *parts = safe_relative(entry["path"])
        target = extractor.destinations[top].joinpath(*parts)
        if not extractor.real_directories(top, tuple(parts[:-1])):
            raise SystemExit(f"a parent directory of {target} is a symbolic link or a file")
        # A /tmp target can be a single file below a directory that the stream does not hold.
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            raise SystemExit(f"{target} exists, although the hand-off recorded it as a model file")
        source = home.joinpath(*blobs_dir, entry["blob"])
        # Root keeps the /tmp targets for every server start, so they get copies: a hard link
        # would let the agent's processes change them through the file in the home.
        if entry["kind"] == "link" and top == HOME:
            try:
                os.link(source, target, follow_symlinks=False)
                continue
            except OSError as error:
                if error.errno != errno.EXDEV:
                    raise
        shutil.copyfile(source, target)
        os.chmod(target, entry["mode"])
        os.utime(target, (entry["mtime"], entry["mtime"]))
    return sum(blob["size"] for blob in model["left_out"])


def unpack(args: argparse.Namespace) -> None:
    with os.fdopen(args.manifest_fd, "rb") as stream:
        manifest = read_manifest(stream)
    extractor = Extractor({HOME: args.home, TMP: args.tmp})
    extractor.extract(sys.stdin.buffer)
    log(f"unpacked: {dict(extractor.counts)}")
    if extractor.counts["refused"]:
        raise SystemExit("some members of the hand-off were refused")
    placed = place_model_files(manifest, extractor, args.staging)
    log(f"put back {placed} bytes of unchanged model files from the fresh download")
    extractor.finish()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("pack")
    command.add_argument("--home", type=Path, required=True)
    command.add_argument("--record", type=Path, required=True)
    command.add_argument("--tmp-list", type=Path, required=True, help="NUL-separated /tmp targets")
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--part-bytes", type=int, default=PART_BYTES)
    command.set_defaults(run=pack)
    command = commands.add_parser("verify")
    command.add_argument("handoff", type=Path)
    command.add_argument("--model", required=True)
    command.add_argument("--revision", required=True)
    command.set_defaults(run=verify)
    command = commands.add_parser("stream")
    command.add_argument("handoff", type=Path)
    command.set_defaults(run=stream_parts)
    command = commands.add_parser("unpack")
    command.add_argument("--manifest-fd", type=int, required=True)
    command.add_argument("--home", type=Path, required=True)
    command.add_argument("--tmp", type=Path, required=True)
    command.add_argument("--staging", type=Path, required=True, help="the fresh download's hub cache")
    command.set_defaults(run=unpack)
    args = parser.parse_args()
    # A file name need not be valid UTF-8, and a log line must not fail on one.
    sys.stdout.reconfigure(errors="backslashreplace")
    args.run(args)


if __name__ == "__main__":
    sys.exit(main())
