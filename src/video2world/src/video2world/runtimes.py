"""Validate operator runtime configuration once for the selected evaluators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v2w.benchmark import Configuration

RUNTIME_BY_EVALUATOR = {
    "fb": "sim",
    "ego_arm": "sim",
    "ego_bimanual": "sim",
    "twin": "twin",
    "twin_toy": "twin",
    "cloth": "twin",
    "robodojo_native_task": "isaac",
    "inhouse": "isaac",
    "inhouse_point_robot": "isaac",
    "inhouse_reviewed": "isaac",
    "inhouse_wallet": "isaac",
    "inhouse_fryer": "isaac",
}
TOOL_NAMES = {
    "python",
    "twin_python",
    "isaac_python",
    "robodojo_source",
    "graphics_libs",
}
REQUIRED_TOOLS = {
    "sim": {"python"},
    "twin": {"python", "twin_python"},
    "isaac": {"python", "isaac_python"},
}


def runtime(evaluator: str) -> str:
    try:
        return RUNTIME_BY_EVALUATOR[evaluator]
    except KeyError:
        raise ValueError(f"unsupported upstream evaluator: {evaluator}") from None


@dataclass(frozen=True)
class Runtime:
    image: str
    tools: dict[str, str]
    mounts: tuple[dict, ...]

    @property
    def python(self) -> str:
        return self.tools["python"]

    @property
    def environment(self) -> dict[str, str]:
        from v2w.paths import TOOLS

        return {TOOLS[field]: value for field, value in self.tools.items()}


def text(config: dict, field: str, label: str) -> str:
    value = config.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a nonempty string")
    return value


def mounts(value: list, label: str) -> tuple[dict, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{label}.mounts must be a list of bind mounts")
    result = []
    for index, mount in enumerate(value):
        location = f"{label}.mounts[{index}]"
        if not isinstance(mount, dict) or mount.get("type") != "bind":
            raise ValueError(f"{location} must be a bind mount object")
        for field in ("source", "target"):
            if not Path(text(mount, field, location)).is_absolute():
                raise ValueError(f"{location}.{field} must be an absolute path")
        result.append(dict(mount, read_only=True))
    return tuple(result)


def load_runtimes(
    path: Path, configurations: list[Configuration]
) -> dict[str, Runtime]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: expected a runtime configuration object")
    required = {}
    for config in configurations:
        name = runtime(config.evaluator)
        required.setdefault(name, set(REQUIRED_TOOLS[name]))
        if config.evaluator == "robodojo_native_task":
            required[name].add("robodojo_source")
    resolved = {}
    for name, fields in required.items():
        config = raw.get(name)
        if not isinstance(config, dict):
            raise TypeError(f"{path}: requires a '{name}' runtime object")
        unknown = config.keys() - (TOOL_NAMES | {"image", "mounts"})
        if unknown:
            raise ValueError(f"runtime {name}: unknown fields {sorted(unknown)}")
        tools = {
            field: text(config, field, name)
            for field in fields | (config.keys() & TOOL_NAMES)
        }
        resolved[name] = Runtime(
            image=text(config, "image", name),
            tools=tools,
            mounts=mounts(config.get("mounts", []), name),
        )
    return resolved
