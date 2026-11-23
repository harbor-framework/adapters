"""File-based test imports keep adapter and upstream ``balrog`` separate."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[2]
PACKAGE = PROJECT / "src" / "balrog"
TEMPLATE = PACKAGE / "task-template"


def load_file(name, path):
    path = Path(path).resolve()
    if name in sys.modules:
        module = sys.modules[name]
        if Path(module.__file__).resolve() != path:
            raise RuntimeError("Conflicting test module: " + name)
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load test target: " + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def configure_upstream():
    value = os.environ.get("BALROG_SOURCE")
    if not value:
        raise RuntimeError("Set BALROG_SOURCE to the pinned upstream BALROG clone before runtime tests")
    source = Path(value).expanduser().resolve()
    if not (source / "balrog/evaluator.py").is_file():
        raise RuntimeError("BALROG_SOURCE does not contain the upstream evaluator")
    loaded = sys.modules.get("balrog")
    if loaded is not None and Path(loaded.__file__).resolve().parent != source / "balrog":
        raise RuntimeError("Adapter balrog was already imported; run runtime tests in a separate Python process")
    sys.path.insert(0, str(source))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    return source


def frozen_case(task_id="babyai-goto-seed-0"):
    manifest = json.loads((PACKAGE / "fixtures/manifest.json").read_text(encoding="utf-8"))
    return next(case for case in manifest["cases"] if case["episode"]["task_id"] == task_id)


def game_server():
    return load_file("_balrog_test_game_server", TEMPLATE / "environment/game_server.py")


def parity_runner():
    return load_file("_balrog_test_parity_runner", PACKAGE / "parity_runner.py")


def harbor_agent():
    return load_file("_balrog_test_harbor_agent", PACKAGE / "agent.py")
