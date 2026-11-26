"""Verified public input and two source blobs for the one supported vLLM task."""
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen

from huggingface_hub import HfFileSystem
from pyarrow.parquet import ParquetFile

REPO = "UKGovernmentBEIS/vllm-control-arena"
DATASET = "RoganInglis/vllm-control-arena"
REVISION = "f6ea5be8a1ef134bef49ff415992fb7365d325f3"
BASE = "0df25101d6dc3b83edeb813534b2d0931c79431a"
GOLD = "ade3f7d98869da44396d21d1c091be7edd3e1c8e"
TITLE = "fix_prefix_cache_metrics_reset"
SLUG = "vllm-fix-prefix-cache-metrics-reset"
SOURCE = "vllm/v1/metrics/loggers.py"
PROMPT_SHA = "dc0e3d442678c5b34f375869f115376f34e0f1a659f8c1157ad3899c34c371ae"
BASE_SHA = "1d556f88a4c8c8868637a4eea26c6aae72f299ea367c391967d73e8b62f80c14"
GOLD_SHA = "fc7357aa0b9f205bf147da35e88b387008c18bc5fa6b87cb53beecba85c83d01"
LICENSE_SHA = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def download(url):
    request = Request(url, headers={"User-Agent": "harbor-vllm-metrics-adapter"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def atomic_cache(path, raw):
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(raw)
    Path(temporary.name).replace(path)


def upstream_row():
    fs = HfFileSystem(token=False)
    location = f"datasets/{DATASET}@{REVISION}/data/train-00000-of-00001.parquet"
    with fs.open(location, "rb") as stream:
        source = ParquetFile(stream)
        for i in range(source.num_row_groups):
            titles = source.read_row_group(i, columns=["task_title"]).column(0).to_pylist()
            if TITLE in titles:
                fields = ["task_title", "task_instructions", "parent_hash", "commit_url", "requires_internet"]
                return source.read_row_group(i, columns=fields).slice(titles.index(TITLE), 1).to_pylist()[0]
    raise ValueError("Pinned main task absent from upstream dataset")


def materialize(cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    metadata = cache / "row.json"
    row = json.loads(metadata.read_bytes()) if metadata.exists() else upstream_row()
    if (row["task_title"] != TITLE or row["parent_hash"] != BASE or row["requires_internet"] is not False
            or row["commit_url"] != f"https://github.com/{REPO}/commit/{GOLD}"
            or digest(row["task_instructions"].encode()) != PROMPT_SHA):
        raise ValueError("Cached or downloaded row differs from the pinned public main task")
    if not metadata.exists():
        atomic_cache(metadata, json.dumps(row).encode())
    blobs = {"baseline.py": (BASE, SOURCE, BASE_SHA), "reference.py": (GOLD, SOURCE, GOLD_SHA),
             "LICENSE": (BASE, "LICENSE", LICENSE_SHA)}
    if any(not (cache / name).exists() for name in blobs):
        commit = json.loads(download(f"https://api.github.com/repos/{REPO}/commits/{GOLD}"))
        if (commit["sha"] != GOLD or [p["sha"] for p in commit["parents"]] != [BASE]
                or [(f["filename"], f["status"]) for f in commit["files"]] != [(SOURCE, "modified")]):
            raise ValueError("Unexpected commit relationship or changed source paths")
    for name, (rev, remote, checksum) in blobs.items():
        path = cache / name
        raw = path.read_bytes() if path.exists() else download(f"https://raw.githubusercontent.com/{REPO}/{rev}/{remote}")
        if digest(raw) != checksum:
            raise ValueError(f"Source digest mismatch for {name}")
        if not path.exists():
            atomic_cache(path, raw)
    return row
