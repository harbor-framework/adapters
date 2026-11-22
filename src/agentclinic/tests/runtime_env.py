import importlib
import json
import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "agentclinic"
RUNTIME_TEMPLATE = PACKAGE_DIR / "task-template" / "environment" / "runtime"
FLAT_MODULES = ("prompts", "clinic", "llm", "server")


def import_runtime(target: Path):
    target.mkdir(parents=True, exist_ok=True)
    for name in ("prompts", "clinic", "llm"):
        shutil.copy(PACKAGE_DIR / f"{name}.py", target / f"{name}.py")
    shutil.copy(RUNTIME_TEMPLATE / "server.py", target / "server.py")
    for name in FLAT_MODULES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(target))
    try:
        return importlib.import_module("server")
    finally:
        sys.path.remove(str(target))


def write_case(path: Path, case) -> Path:
    path.write_text(json.dumps(case.runtime_view()))
    return path
