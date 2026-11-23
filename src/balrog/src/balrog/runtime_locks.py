"""Stage complete, captured runtime locks into self-contained task contexts."""
import hashlib
import json
from pathlib import Path


def stage_runtime_lock(package: Path, environment: str, destination: Path) -> None:
    root = package / "runtime-locks"
    inventory = json.loads((root / "inventory.json").read_text(encoding="utf-8"))
    runtime = inventory["environments"][environment]
    lock = {"schema_version": 1, "environment": environment,
            "base_image": inventory["base_image"], "python": inventory["python"],
            "apt_snapshot": inventory["apt_snapshot"], **runtime}
    for source, target in ((f"{environment}.requirements.lock", "requirements-game.lock"),
                           (f"{environment}.apt.lock", "apt-game.lock")):
        content = (root / source).read_bytes()
        lock[target + "_sha256"] = hashlib.sha256(content).hexdigest()
        (destination / target).write_bytes(content)
    (destination / "runtime-lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
