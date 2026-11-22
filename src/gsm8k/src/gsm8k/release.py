"""Freeze verified GSM8K data and split-level native evidence."""

import argparse
from collections import Counter
import gzip
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory

from .acceptance import load
from .adapter import HARBOR_VERSION, SPLITS


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def control_key(split, record):
    return split, record["task_digest"], record["case"]


def expected_controls(plans, datasets):
    expected, hashes = {}, {}
    for split in SPLITS:
        hashes[split] = file_sha(datasets / f"gsm8k-{split}" / "manifest.json")
    for path in sorted(plans.glob("*/*.json")):
        plan = load(path)
        split = plan["split"]
        if plan["manifest_sha256"] != hashes[split]:
            raise ValueError(f"Plan manifest differs for {path}")
        for record in plan["records"]:
            key = control_key(split, record)
            if key in expected:
                raise ValueError(f"Duplicate planned control: {key}")
            expected[key] = record
    counts = Counter(key[0] for key in expected)
    if counts != {split: 2 * spec[2] + 3 for split, spec in SPLITS.items()}:
        raise ValueError(f"Unexpected planned coverage: {counts}")
    return expected, hashes


def valid_receipt(row, expected):
    keys = ("task_name", "source_row", "source_line_sha256")
    return (all(row[key] == expected[key] for key in keys)
            and row["harbor_version"] == HARBOR_VERSION and row["provider"] in ("docker", "podman")
            and row["reward"] == row["upstream_reward"] == expected["expected_reward"]
            and row["submission_sha256"] == sha256(expected["submission"].encode()).hexdigest())


def collect_receipts(paths, expected, hashes):
    received, failed = {}, {split: [] for split in SPLITS}
    seen_ids = set()
    for path in paths:
        evidence = load(path)
        split = evidence["split"]
        if evidence["manifest_sha256"] != hashes[split]:
            raise ValueError(f"Native evidence manifest differs: {path}")
        failed[split].extend(evidence["unscored"])
        for row in evidence["receipts"]:
            key = control_key(split, row)
            if key in received or row["trial_id"] in seen_ids:
                raise ValueError(f"Duplicate scored control or trial: {key}")
            if key not in expected or not valid_receipt(row, expected[key]):
                raise ValueError(f"Unmatched native evidence: {key}")
            received[key] = row
            seen_ids.add(row["trial_id"])
    if missing := expected.keys() - received.keys():
        raise ValueError(f"Cannot freeze without all native results: {len(missing)} controls outstanding")
    return received, failed


def archive_member(archive, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o755 if name.endswith(".sh") else 0o644
    archive.addfile(info, BytesIO(data))


def task_members(archive, dataset, task):
    for filename, digest in sorted(task["files"].items()):
        member = f"{task['task_name']}/{filename}"
        data = (dataset / member).read_bytes()
        if sha256(data).hexdigest() != digest:
            raise ValueError(f"Task file drift: {member}")
        archive_member(archive, member, data)


def write_archive(dataset, path, manifest):
    licences = {"LICENSE": Path(__file__).parents[2] / "LICENSE",
                "LICENSE.openai": Path(__file__).with_name("LICENSE.openai")}
    with path.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
        with tarfile.open(fileobj=stream, mode="w|") as archive:
            for name, location in licences.items():
                archive_member(archive, name, location.read_bytes())
            for name in ("dataset.toml", "manifest.json"):
                archive_member(archive, name, (dataset / name).read_bytes())
            for task in manifest["tasks"]:
                task_members(archive, dataset, task)


def freeze_split(staged, dataset, rebuild, split, records, failures):
    manifest = load(dataset / "manifest.json")
    for name in ("dataset.toml", "manifest.json"):
        data = (dataset / name).read_bytes()
        if data != (rebuild / name).read_bytes():
            raise ValueError(f"Independent rebuild differs: {split} {name}")
        (staged / f"{split}-{name}").write_bytes(data)
    archive = staged / f"{split}-tasks.tar.gz"
    write_archive(dataset, archive, manifest)
    evidence = {
        "split": split, "task_count": manifest["task_count"], "harbor_version": HARBOR_VERSION,
        "source": manifest["source"], "task_archive_sha256": file_sha(archive),
        "manifest_sha256": file_sha(dataset / "manifest.json"),
        "receipts": [row for key, row in sorted(records.items()) if key[0] == split],
        "unscored": failures[split],
    }
    raw = (json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (staged / f"{split}-native.json.gz").write_bytes(gzip.compress(raw, mtime=0))


def freeze(datasets, rebuilt, plans, evidence_paths, output):
    expected, hashes = expected_controls(plans, datasets)
    receipts, failures = collect_receipts(evidence_paths, expected, hashes)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".gsm8k-freeze-", dir=output.parent) as directory:
        staged = Path(directory) / "release"
        staged.mkdir()
        for split in SPLITS:
            name = f"gsm8k-{split}"
            freeze_split(staged, datasets / name, rebuilt / name, split, receipts, failures)
        sums = [f"{file_sha(path)}  {path.name}\n" for path in sorted(staged.iterdir())]
        (staged / "SHA256SUMS").write_text("".join(sums), encoding="utf-8")
        staged.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("datasets", "rebuilt", "plans", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    args = parser.parse_args()
    paths = [path for item in args.evidence for path in (sorted(item.rglob("evidence.json"))
                                                       if item.is_dir() else [item])]
    freeze(args.datasets, args.rebuilt, args.plans, paths, args.output)


if __name__ == "__main__":
    main()
