"""Verify every local subject file against the pinned public model manifest."""

import hashlib
from pathlib import Path

REVISION = "1feab8ac771d33eddd9070ceca133802be9b917b"
BASE = Path("/models/hub/models--FabienRoger--cot_5k")
FILES = {
    "config.json": "ea72d86ff8157c87d082f2650ca00a43b48a5d12",
    "generation_config.json": "c7fff9d731a514d94f8b2d1217031a9bdf313f70",
    "merges.txt": "354558edcdbd64ca7abd407b8be3d5d09d39d781",
    "model.safetensors": "fd70832be22090694b99ddb73e80d5c957440d25636ff8b44f08be4619f1ccfc",
    "special_tokens_map.json": "fc7198c952bd37e5634aea82c6b43e72e510b9e1",
    "tokenizer.json": "c304174e75a85cae967339164c47c344bdc1749a",
    "tokenizer_config.json": "2d01cbb1c178fa8e01361f35b3a40b3867aec71a",
    "vocab.json": "9a8a4e98f76ab0fd29712d0fe7e9abd9dc07de59",
}


def main() -> None:
    for name, expected in FILES.items():
        path = BASE / "snapshots" / REVISION / name
        if len(expected) == 64:
            with path.open("rb") as file:
                digest = hashlib.file_digest(file, "sha256").hexdigest()
        else:
            body = path.read_bytes()
            digest = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
        if digest != expected:
            raise ValueError(f"Unexpected file content in {name}")
    (BASE / "refs").mkdir()
    (BASE / "refs/main").write_text(REVISION)


if __name__ == "__main__":
    main()
