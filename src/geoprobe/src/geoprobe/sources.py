"""Content-addressed upstream inputs. Task assets are downloaded, not vendored."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

ARENA_COMMIT = "ce298e7952b9138fd05796e33a2b8de63a0e404c"
DATASET_COMMIT = "5f729375eb35163a024625dd8ea72ac57a427a24"
HARBOR_COMMIT = "99218a4611e3bd76e49ce3b5f977e8c8134ad3ac"
DATASET_REPO = "uuu-Quant/Embodied-Agent-Arena"
BASE_URL = f"https://huggingface.co/datasets/{DATASET_REPO}/resolve/{DATASET_COMMIT}"
RECEIPT_SHA256 = "e5ef0f5a9427550c75ba7a1e9cc1dd17a871e053b723be64e33b883d7f0a4b66"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(value: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in value:
        raise ValueError(f"Unsafe upstream asset path: {value}")
    return Path(*path.parts)


def fetch_file(remote: str, target: Path, expected: str | None = None) -> None:
    if target.is_file() and (expected is None or sha256(target) == expected):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".partial")
    try:
        with urlopen(f"{BASE_URL}/{remote}", timeout=120) as response:
            temporary.write_bytes(response.read())
        if expected and sha256(temporary) != expected:
            raise ValueError(f"SHA256 mismatch for {remote}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def load_cases(data_root: Path) -> list[dict]:
    receipt = data_root / "download_receipt.json"
    if sha256(receipt) != RECEIPT_SHA256:
        raise ValueError("GeoProbe receipt is not the pinned release")
    files = json.loads(receipt.read_text())["files"]
    if sha256(data_root / "catalog.jsonl") != files["catalog.jsonl"]:
        raise ValueError("GeoProbe catalog checksum mismatch")
    cases = [json.loads(line) for line in (data_root / "catalog.jsonl").read_text().splitlines() if line.strip()]
    if len(cases) != 168 or len({case["sample_id"] for case in cases}) != 168:
        raise ValueError("Expected exactly 168 unique GeoProbe cases")
    for case in cases:
        for item in case["images"]:
            path = safe_relative(item["path"])
            if files.get(item["path"]) != item["sha256"]:
                raise ValueError(f"Catalog/receipt mismatch: {path}")
    return sorted(cases, key=lambda case: case["sample_id"])


def download(data_root: Path) -> list[dict]:
    """Fetch only the GeoProbe closure, never the other 832 Arena tasks."""
    prefix = "assets/w1_geoprobe"
    fetch_file(f"{prefix}/download_receipt.json", data_root / "download_receipt.json", RECEIPT_SHA256)
    receipt = json.loads((data_root / "download_receipt.json").read_text())
    fetch_file(f"{prefix}/catalog.jsonl", data_root / "catalog.jsonl", receipt["files"]["catalog.jsonl"])
    cases = load_cases(data_root)
    assets = {item["path"]: item["sha256"] for case in cases for item in case["images"]}

    def fetch(item):
        relative, expected = item
        fetch_file(f"{prefix}/{relative}", data_root / safe_relative(relative), expected)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, sorted(assets.items())))
    return cases
