from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from . import DATA_REVISION, MANIFEST_SHA256, UPSTREAM_REVISION
from .release import key, load_upstream, read_manifest, task_id
from .runtimes import Runtime, load_runtimes, runtime

if TYPE_CHECKING:
    from v2w.benchmark import Configuration

TEMPLATE = Path(__file__).parent / "task-template"
GPU = {
    "deploy": {
        "resources": {
            "reservations": {
                "devices": [{"driver": "nvidia", "count": 1, "capabilities": ["gpu"]}]
            }
        }
    }
}


# Fixed before model outcomes: all profile/evaluator pairs, then additional families.
PARITY_TASK_IDS = frozenset(
    (
        "bulb-insert/fbraw_2023-01-22-22_45_54_lamp_bulb",
        "cabinet-door/fbraw_2023-01-24-00_54_49_cabinet_door_right",
        "dexycb-lift-arm/dexycb_s01_141931",
        "dexycb-lift-bimanual/dexycb_s01_141931",
        "droid-cloth-fold/droid_iliad_2023_08_17_21h_40m_43s_towel_cloth",
        "droid-pick-place/droid_autolab_2023_07_14_15h_59m_42s_bowl_hand",
        "inhouse-episode-initially-held-place/inhouse_071c4ac3_task18_episode_r001",
        "inhouse-fryer-pull-and-release/inhouse_06766809_task66_fryer_r021",
        "inhouse-point-origin-pick-and-hold/inhouse_0048dd8e_task61_point_robot_r001",
        "inhouse-reviewed-initially-held-insert/inhouse_00478d72_task72_reviewed_r001",
        "inhouse-wallet-initially-held-insert/inhouse_042b3b16_task74_wallet_robot_r001",
        "push-t/twin_pusht_demo_0",
        "robodojo-task-x5-r1/robodojo_arrange_largest_number_7_x5__r002",
        "rope-route/twin_rope_replay_1",
        "toy-pack/twin_toy_demo_1",
        "cabinet-top/fbraw_2023-01-24-00_51_55_cabinet_top",
        "chair-back/fbraw_2023-01-27-00_28_15_chair_back",
        "chair-nut/fbraw_2023-01-27-00_50_47_chair_nut1",
        "drawer-insert/fbraw_2023-01-23-04_10_30_drawer_container_top",
        "hoi4d-pickplace-arm/hoi4d_bottle_c5n29s258s03t2_alignrgb_f042_128_pickplace",
        "hoi4d-pickplace-bimanual/hoi4d_bottle_c5n29s258s03t2_alignrgb_f042_128_pickplace",
        "hood-place/fbraw_2023-01-22-22_47_54_lamp_hood",
    )
)


class Video2WorldAdapter:
    def __init__(
        self,
        upstream_root: Path,
        data_root: Path,
        output_dir: Path,
        runtime_config: Path,
        *,
        task_ids: list[str] | None = None,
        limit: int | None = None,
        overwrite: bool = False,
        split: str = "full",
    ):
        self.upstream = upstream_root.resolve()
        self.data = data_root.resolve()
        self.output_dir = output_dir.resolve()
        self.runtime_config = runtime_config
        self.task_ids, self.limit, self.overwrite, self.split = (
            task_ids,
            limit,
            overwrite,
            split,
        )

    def run(self) -> list[Path]:
        load_upstream(self.upstream, self.data)
        from v2w import benchmark

        rows = self._select(read_manifest(self.data))
        configurations = [
            benchmark.Configuration(r["family"], r["sample"], r["metric_family"])
            for r in rows
        ]
        runtimes = load_runtimes(self.runtime_config, configurations)
        ids = [task_id(config.key) for config in configurations]
        if len(set(ids)) != len(ids):
            raise ValueError("sanitized task names collide")
        if self.output_dir.exists() and any(self.output_dir.iterdir()):
            if not self.overwrite:
                raise FileExistsError(
                    f"{self.output_dir} is not empty; use --overwrite"
                )
            if not (self.output_dir / "selection.json").is_file():
                raise ValueError(
                    "--overwrite requires an existing generated cohort with selection.json"
                )
        for config in configurations:
            if not config.profile:
                raise ValueError(f"no upstream agent profile: {config.key}")
            for name in ("video.mp4", "meta.json"):
                path = self.data / "samples" / config.sample / name
                if not path.is_file():
                    raise FileNotFoundError(
                        f"missing upstream input: {path}; download data revision {DATA_REVISION}"
                    )
        self.output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=self.output_dir.parent, prefix=".v2w-"
        ) as tmp:
            cohort = Path(tmp) / "cohort"
            cohort.mkdir()
            for config in configurations:
                self._generate(config, runtimes[runtime(config.evaluator)], cohort)
            (cohort / "selection.json").write_text(
                json.dumps(
                    {
                        "upstream_revision": UPSTREAM_REVISION,
                        "data_revision": DATA_REVISION,
                        "manifest_sha256": MANIFEST_SHA256,
                        "split": self.split,
                        "configurations": rows,
                        "task_directories": ids,
                    },
                    indent=2,
                )
                + "\n"
            )
            self._publish(cohort)
        return [self.output_dir / name for name in ids]

    def _select(self, rows: list[dict]) -> list[dict]:
        if self.split == "parity":
            rows = [row for row in rows if key(row) in PARITY_TASK_IDS]
        if self.task_ids is not None:
            unknown = set(self.task_ids) - {key(r) for r in rows}
            if unknown:
                raise ValueError(
                    f"unknown task IDs in {self.split}: {sorted(unknown)}; use family/sample"
                )
            rows = [r for r in rows if key(r) in self.task_ids]
        if self.limit is not None:
            if self.limit <= 0:
                raise ValueError("--limit must be positive")
            rows = rows[: self.limit]
        return rows

    def _publish(self, cohort: Path) -> None:
        if not self.output_dir.exists():
            cohort.rename(self.output_dir)
            return
        # Outside the staging tree so a failed rollback cannot delete the old cohort.
        previous = self.output_dir.with_name(
            f".{self.output_dir.name}.previous-{secrets.token_hex(8)}"
        )
        self.output_dir.rename(previous)
        try:
            cohort.rename(self.output_dir)
        except OSError:
            try:
                previous.rename(self.output_dir)
            except OSError as exc:
                raise RuntimeError(
                    f"publication failed; previous cohort retained at {previous}"
                ) from exc
            raise
        shutil.rmtree(previous)

    def _generate(
        self, configuration: Configuration, config: Runtime, output: Path
    ) -> None:
        row = {
            "family": configuration.family,
            "sample": configuration.sample,
            "metric_family": configuration.spec,
        }
        with tempfile.TemporaryDirectory(dir=output, prefix=".prepare-") as tmp:
            task = Path(tmp) / "task"
            shutil.copytree(TEMPLATE, task)
            public = task / "environment/public"
            public.mkdir()
            env = dict(
                os.environ,
                PYTHONPATH=str(self.upstream),
                V2W_DATA=str(self.data),
                V2W_AGENT_LOCAL=str(Path(tmp) / "agent-local"),
                **config.environment,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "v2w.agents.run",
                    "--profile",
                    configuration.profile,
                    "--sample",
                    str(self.data / "samples" / row["sample"]),
                    "--out",
                    str(public / "pkg"),
                    "--prepare",
                    str(public / "task"),
                ],
                cwd=self.upstream,
                env=env,
                check=True,
            )
            shutil.copytree(
                Path(tmp) / "agent-local/lib/video2sim", public / "lib/video2sim"
            )
            shutil.copyfile(self.upstream / "LICENSE", public / "lib/LICENSE")
            # The cloth brief invokes this public, GT-free contract by module name.
            for rel in (
                "v2w/__init__.py",
                "v2w/tracks/__init__.py",
                "v2w/tracks/cloth/__init__.py",
                "v2w/tracks/cloth/contract.py",
            ):
                target = public / "lib" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.upstream / rel, target)
            replacements = {
                str(public / "task"): "/workspace/task",
                str(public / "pkg"): "/workspace/pkg",
                str(Path(tmp) / "agent-local/lib"): "/opt/video2world",
                str(self.upstream): "/opt/video2world",
            }
            for path in public.rglob("*"):
                if path.is_file() and path.suffix in (".md", ".json"):
                    text = path.read_text()
                    for old, new in replacements.items():
                        text = text.replace(old, new)
                    path.write_text(text)
            (task / "instruction.md").write_text((public / "task/brief.md").read_text())
            config_text = (
                (task / "task.toml")
                .read_text()
                .replace("{task_id}", task_id(configuration.key))
            )
            (task / "task.toml").write_text(config_text)
            test_script = task / "tests/test.sh"
            test_script.write_text(
                test_script.read_text().replace("{python}", shlex.quote(config.python))
            )
            bridge = Path(__file__).with_name("bridge.py")
            for target in (
                task / "environment/client.py",
                task / "environment/evaluator_service.py",
                task / "tests/verifier.py",
            ):
                shutil.copyfile(bridge, target)
            service = {
                "configuration": row,
                "upstream_revision": UPSTREAM_REVISION,
                "manifest_sha256": MANIFEST_SHA256,
                "runtime": runtime(configuration.evaluator),
                "tools": config.tools,
                "source_files": {
                    str(p.relative_to(self.upstream)): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for folder in ("v2w", "video2sim")
                    for p in sorted((self.upstream / folder).rglob("*"))
                    if p.is_file()
                    and "__pycache__" not in p.parts
                    and p.suffix != ".pyc"
                },
            }
            project = tomllib.loads((self.upstream / "pyproject.toml").read_text())[
                "project"
            ]
            rt = runtime(configuration.evaluator)
            service["requirements"] = project["dependencies"] + (
                project["optional-dependencies"][rt] if rt in ("sim", "twin") else []
            )
            for directory in ("environment", "tests"):
                (task / directory / "evaluator.json").write_text(
                    json.dumps(service, indent=2) + "\n"
                )
            (task / "environment/docker-compose.yaml").write_text(
                yaml.safe_dump(self._compose(config), sort_keys=False)
            )
            (task / "tests/docker-compose.yaml").write_text(
                yaml.safe_dump(self._verifier_compose(config), sort_keys=False)
            )
            task.rename(output / task_id(configuration.key))

    def _evaluation_runtime(self, config: Runtime) -> dict:
        return {
            "working_dir": "/opt/video2world",
            "volumes": [
                {
                    "type": "bind",
                    "source": str(self.upstream),
                    "target": "/opt/video2world",
                    "read_only": True,
                },
                {
                    "type": "bind",
                    "source": str(self.data),
                    "target": "/data",
                    "read_only": True,
                },
                *config.mounts,
            ],
            "environment": {
                "V2W_DATA": "/data",
                "NVIDIA_DRIVER_CAPABILITIES": "all",
                "PYTHONDONTWRITEBYTECODE": "1",
                **config.environment,
            },
            "shm_size": "4gb",
            **GPU,
        }

    def _compose(self, config: Runtime) -> dict:
        checker = self._evaluation_runtime(config)
        checker.update(
            {
                "image": config.image,
                "entrypoint": [config.python, "/adapter/service.py", "serve"],
            }
        )
        checker["volumes"].extend(
            [
                {
                    "type": "bind",
                    "source": "${CONTEXT_DIR}/evaluator_service.py",
                    "target": "/adapter/service.py",
                    "read_only": True,
                },
                {
                    "type": "bind",
                    "source": "${CONTEXT_DIR}/evaluator.json",
                    "target": "/adapter/config.json",
                    "read_only": True,
                },
            ]
        )
        return {
            "services": {
                "main": {
                    "build": {
                        "args": {
                            "RUNTIME_IMAGE": config.image,
                            "PUBLIC_PYTHON": config.python,
                        }
                    },
                    "depends_on": {"evaluator": {"condition": "service_started"}},
                    "environment": {"NVIDIA_DRIVER_CAPABILITIES": "all"},
                    **GPU,
                },
                "evaluator": checker,
            }
        }

    def _verifier_compose(self, config: Runtime) -> dict:
        verifier = self._evaluation_runtime(config)
        verifier["build"] = {"args": {"RUNTIME_IMAGE": config.image}}
        return {"services": {"main": verifier}}
