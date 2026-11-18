"""Generate Harbor tasks for CAVA (pipeline / transcript variant).

Each task corresponds to one CAVA record. The agent sees exactly what CAVA's OpenAI
pipeline gives its LLM stage: the pipeline preamble, the ASR transcript wrapped in
``[BEGIN AUDIO] ... [END AUDIO]``, and the CAVA task prompt. Records and transcripts
come from manifests built by ``prepare/prepare_manifests.py`` (one JSONL per subtask).
"""

from __future__ import annotations

import base64
import json
import logging
import shutil
from pathlib import Path

from .subtasks import SUBTASKS, Subtask

LOGGER = logging.getLogger(__name__)

PKG_DIR = Path(__file__).parent
TEMPLATE_DIR = PKG_DIR / "task-template"
SCORING_DIR = PKG_DIR / "scoring"
DEFAULT_MANIFEST_DIR = PKG_DIR / "manifests"
FUNCTIONS_FILE = PKG_DIR / "data" / "functions.json"
PARITY_IDS_FILE = PKG_DIR / "data" / "parity_ids.json"

ANSWER_PATH = "/app/answer.txt"
CALLS_PATH = "/app/function_calls.jsonl"


def task_id_for(subtask: str, item_id: str) -> str:
    return f"{subtask.replace('_', '-')}-{item_id}"


class CavaAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        manifest_dir: Path | None = None,
        subtasks: list[str] | None = None,
        split: str = "full",
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = set(task_ids) if task_ids else None
        self.manifest_dir = Path(manifest_dir or DEFAULT_MANIFEST_DIR)
        self.subtasks = subtasks or list(SUBTASKS)
        self.split = split

    def _load_manifest(self, subtask: str) -> list[dict]:
        path = self.manifest_dir / f"{subtask}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"manifest missing: {path} (run prepare/prepare_manifests.py)")
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def run(self) -> list[Path]:
        parity_ids = json.loads(PARITY_IDS_FILE.read_text()) if self.split == "parity" else None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for subtask in self.subtasks:
            spec = SUBTASKS[subtask]
            rows = self._load_manifest(subtask)
            if parity_ids is not None:
                keep = set(parity_ids.get(subtask, []))
                rows = [r for r in rows if r["item_id"] in keep]
                missing = keep - {r["item_id"] for r in rows}
                if missing:
                    raise ValueError(f"{subtask}: {len(missing)} parity ids missing from "
                                     f"the manifest, e.g. {sorted(missing)[:3]}")
            for row in rows:
                task_id = task_id_for(subtask, row["item_id"])
                if self.task_ids and task_id not in self.task_ids:
                    continue
                if self.limit is not None and len(written) >= self.limit:
                    return written
                task_dir = self.output_dir / task_id
                if task_dir.exists():
                    if not self.overwrite:
                        continue
                    shutil.rmtree(task_dir)
                self._write_task(task_dir, task_id, spec, row)
                written.append(task_dir)
        LOGGER.info("Wrote %d tasks to %s", len(written), self.output_dir)
        return written

    def _write_task(self, task_dir: Path, task_id: str, spec: Subtask, row: dict) -> None:
        record, transcript = row["record"], row["transcript"]
        if transcript is None:
            raise ValueError(f"{task_id}: manifest row has no transcript")
        shutil.copytree(TEMPLATE_DIR, task_dir)
        messages = spec.pipeline_messages(record, transcript)

        # instruction.md: the two pipeline messages + where to put the answer
        if spec.function_calling:
            how = (
                "Make function calls with the `call_function` command, e.g. "
                "`call_function get_weather '{\"location\": \"Paris\"}'`. It prints the mock "
                "response for each call. The available functions (OpenAI tool schema) are in "
                "`/app/functions.json`. When you are done calling functions, write your final "
                f"response to the user to `{ANSWER_PATH}`."
            )
        else:
            how = f"Write your response to `{ANSWER_PATH}`."
        instruction = "\n\n".join(m["content"].rstrip() for m in messages) + "\n\n---\n\n" + how + "\n"
        (task_dir / "instruction.md").write_text(instruction)

        # task.json: everything the parity agent needs to rebuild the exact pipeline call
        env_dir = task_dir / "environment"
        (env_dir / "task.json").write_text(
            json.dumps({"subtask": spec.name, "messages": messages,
                        "speech_output": spec.speech_output,
                        "function_calling": spec.function_calling}, indent=2)
        )
        if spec.function_calling:
            shutil.copy(FUNCTIONS_FILE, env_dir / "functions.json")
        else:
            (env_dir / "functions.json").write_text("[]\n")

        tests_dir = task_dir / "tests"
        for f in SCORING_DIR.glob("*.py"):
            shutil.copy(f, tests_dir / f.name)
        (tests_dir / "record.json").write_text(
            json.dumps({"subtask": spec.name, "record": record}, indent=2)
        )

        oracle = row["oracle"]
        solve = (task_dir / "solution" / "solve.sh").read_text()
        solve = solve.replace(
            "{{ORACLE_B64}}", base64.b64encode(json.dumps(oracle).encode()).decode()
        )
        (task_dir / "solution" / "solve.sh").write_text(solve)

        toml = (task_dir / "task.toml").read_text()
        for key, value in {
            "TASK_ID": task_id,
            "SUBTASK": spec.name,
            "ITEM_ID": row["item_id"],
            "METRIC": spec.metric,
        }.items():
            toml = toml.replace("{{" + key + "}}", value)
        (task_dir / "task.toml").write_text(toml)
        for script in ("solution/solve.sh", "tests/test.sh"):
            (task_dir / script).chmod(0o755)
