"""
FinSearchComp adapter.

Converts FinSearchComp questions into Harbor task directories.

Scope (593 questions):
- T2 Simple Historical Lookup (219) and T3 Complex Historical Investigation (172),
  from data/finsearchcomp_data.json.
- T1 Time-Sensitive Data Fetching (202), from data/finsearchcomp_akshare_version.json,
  the split upstream grades with the free AkShare API. Upstream has 203 such
  questions; (T1)..._096 is left out because upstream's own lookup raises
  ValueError on its tag/method pair, so it can never be graded.

T1 ground truth is live market data. The adapter can embed a dated snapshot in
each T1 task (--t1-snapshot-dir). The verifier uses it only on the same UTC day
and fetches live data otherwise. See tests/t1_ground_truth.py.

Source: https://github.com/randomtutu/FinSearchComp (pinned commit below)
Paper: https://arxiv.org/abs/2509.13160
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import sys
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"

SOURCE_COMMIT = "55b6393fcf3c8f749ba5a69a70b20d4ef6f67caf"
SOURCE_BASE = f"https://raw.githubusercontent.com/randomtutu/FinSearchComp/{SOURCE_COMMIT}/data"
MAIN_FILE = "finsearchcomp_data.json"
AKSHARE_FILE = "finsearchcomp_akshare_version.json"
SOURCE_SHA256 = {
    MAIN_FILE: "6437a6dae907ec81002bd817dafc26c3e46e6b6edfde700f22645b1e2aa208c4",
    AKSHARE_FILE: "9a0cf3a319fe3d154d54127f6f9d6bac8bbe5eea34d99167a3eed5add2d540d6",
}

TIERS = ("t1", "t2", "t3")
TASK_ORG = "bytedance-seed"
DATASET_NAME = "finsearchcomp"

# Upstream lookup raises ValueError for this question ("指数" + akshare_global_index).
# Keyed by (prompt_id, tags): Greater China and Global questions share prompt ids.
EXCLUDED_T1 = {("(T1)Time_Sensitive_Data_Fetching_096", "指数")}
# T1 tags that upstream routes to non-Chinese markets; the rest are Greater China.
GLOBAL_T1_TAGS = {"Stock", "Index"}

VERIFIER_TIMEOUT_SEC = {"t1": 1800.0, "t2": 600.0, "t3": 600.0}

# Heredoc delimiter used by solve.sh; must not appear in any oracle answer.
HEREDOC_DELIMITER = "FINSEARCHCOMP_REFERENCE_EOF"


def sanitize(identifier: str) -> str:
    """Lowercase and replace every run of non-alphanumerics with a hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", identifier.lower()).strip("-")


def load_records(name: str, data_file: Path | None) -> list[dict]:
    """Load a pinned upstream JSON file, from a local copy or the pinned URL."""
    if data_file is not None:
        raw = Path(data_file).read_bytes()
    else:
        url = f"{SOURCE_BASE}/{name}"
        logger.info("Downloading %s", url)
        with urllib.request.urlopen(url, timeout=60) as resp:
            raw = resp.read()

    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256[name]:
        raise ValueError(
            f"{name} sha256 {digest} does not match pinned {SOURCE_SHA256[name]}. "
            f"Use data/{name} from commit {SOURCE_COMMIT}."
        )
    return json.loads(raw)


def _t1_module():
    """The verifier's T1 helper, imported here to build snapshots (needs akshare)."""
    tests_dir = str(TEMPLATE_DIR / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    try:
        import t1_ground_truth
    except ImportError as e:
        raise RuntimeError(
            "T1 snapshots need akshare and pandas: run with `uv run --extra t1 finsearchcomp ...`"
        ) from e
    return t1_ground_truth


class FinSearchCompTask:
    """One FinSearchComp question."""

    def __init__(self, record: dict):
        self.record = record
        self.prompt_id: str = record["prompt_id"]
        self.prompt: str = record["prompt"]
        self.response_reference: str = record["response_reference"]
        self.judge_system_prompt: str = record["judge_system_prompt"]
        self.judge_prompt_template: str = record["judge_prompt_template"]
        self.tier = self.prompt_id[1:3].lower()  # "t1", "t2" or "t3"
        if self.tier == "t1":
            # The AkShare split has no label, and Greater China and Global
            # questions share prompt ids; upstream's tag decides the market.
            global_q = record["tags"] in GLOBAL_T1_TAGS
            self.region = "global" if global_q else "greater-china"
            self.label = (
                "Time-Sensitive_Data_Fetching(Global)"
                if global_q
                else "Time-Sensitive_Data_Fetching(Greater China)"
            )
            self.id = f"{sanitize(self.prompt_id)}-{self.region}"
        else:
            self.label: str = record["label"]
            self.region = "greater-china" if "Greater China" in self.label else "global"
            self.id = sanitize(self.prompt_id)
        self.snapshot: dict | None = None

    def task_data(self) -> dict:
        data = {
            "prompt_id": self.prompt_id,
            "tier": self.tier,
            "prompt": self.prompt,
            "response_reference": self.response_reference,
            "judge_system_prompt": self.judge_system_prompt,
            "judge_prompt_template": self.judge_prompt_template,
            "label": self.label,
        }
        if self.tier == "t1":
            data["akshare_ticker"] = self.record["akshare_ticker"]
            data["tags"] = self.record["tags"]
            data["method"] = self.record.get("method")
            data["snapshot"] = self.snapshot
        return data

    def oracle_answer(self) -> str:
        if self.tier != "t1":
            return self.response_reference
        # T1 references are rubrics; the oracle replies with the snapshot quote.
        return self.snapshot["ground_truth"] if self.snapshot else ""


class FinSearchCompAdapter:
    """Generates Harbor tasks for FinSearchComp T1, T2 and T3."""

    NAME = DATASET_NAME

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        data_file: Path | None = None,
        akshare_data_file: Path | None = None,
        tiers: list[str] | None = None,
        t1_snapshot_dir: Path | None = None,
        fetch_t1_snapshot: bool = False,
        **kwargs: object,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.data_file = data_file
        self.akshare_data_file = akshare_data_file
        self.tiers = list(tiers or TIERS)
        unknown = set(self.tiers) - set(TIERS)
        if unknown:
            raise ValueError(f"Unknown tiers: {sorted(unknown)}")
        self.t1_snapshot_dir = Path(t1_snapshot_dir) if t1_snapshot_dir else None
        self.fetch_t1_snapshot = fetch_t1_snapshot
        if fetch_t1_snapshot and self.t1_snapshot_dir is None:
            raise ValueError("--fetch-t1-snapshot needs --t1-snapshot-dir")
        self.tasks: list[FinSearchCompTask] = []
        self.generated_count = 0

    def _load_tasks(self) -> None:
        records: list[dict] = []
        if {"t2", "t3"} & set(self.tiers):
            prefixes = tuple(f"({t.upper()})" for t in self.tiers if t != "t1")
            records += [
                r
                for r in load_records(MAIN_FILE, self.data_file)
                if r["prompt_id"].startswith(prefixes)
            ]
        if "t1" in self.tiers:
            records += [
                r
                for r in load_records(AKSHARE_FILE, self.akshare_data_file)
                if r["prompt_id"].startswith("(T1)")
                and (r["prompt_id"], r.get("tags")) not in EXCLUDED_T1
            ]
        self.tasks = sorted((FinSearchCompTask(r) for r in records), key=lambda t: t.id)
        ids = [t.id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("Sanitized task ids are not unique")

    def _attach_snapshots(self, tasks: list[FinSearchCompTask]) -> None:
        t1_tasks = [t for t in tasks if t.tier == "t1"]
        if not t1_tasks:
            return
        if self.t1_snapshot_dir is None:
            logger.warning(
                "No --t1-snapshot-dir: %d T1 tasks will fetch live data at grading time, "
                "and their oracle has no answer.",
                len(t1_tasks),
            )
            return

        g = _t1_module()
        snap_dir = str(self.t1_snapshot_dir.resolve())
        if self.fetch_t1_snapshot:
            needed: list[str] = []
            for t in t1_tasks:
                for u in g.required_universes(
                    t.record["akshare_ticker"], t.record["tags"], t.record.get("method")
                ):
                    if u not in needed:
                        needed.append(u)
            logger.info("Fetching T1 market snapshot (%s) into %s", ", ".join(needed), snap_dir)
            g.fetch_live(needed, snap_dir)

        dates = set()
        missing = 0
        for t in t1_tasks:
            universes = g.required_universes(
                t.record["akshare_ticker"], t.record["tags"], t.record.get("method")
            )
            files = g.snapshot_files(snap_dir, universes)
            fetched_at = min(g.snapshot_timestamp(p) for p in files.values())
            value = g.ground_truth_from_snapshot(t.record, snap_dir)
            if value is None:
                missing += 1
                continue  # no snapshot: the verifier fetches live data
            t.snapshot = {
                "ground_truth": str(value),
                "date": fetched_at.date().isoformat(),
                "fetched_at": fetched_at.isoformat(),
                "files": sorted(Path(p).name for p in files.values()),
            }
            if HEREDOC_DELIMITER in t.snapshot["ground_truth"]:
                raise ValueError(f"Heredoc delimiter found in snapshot for {t.id}")
            dates.add(t.snapshot["date"])
        logger.info(
            "T1 snapshot date(s) (UTC): %s; %d of %d T1 tasks have no ticker in the snapshot",
            ", ".join(sorted(dates)) or "none",
            missing,
            len(t1_tasks),
        )

    def _prepare_task(self, task: FinSearchCompTask, task_dir: Path) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)

        # environment/
        env_dir = task_dir / "environment"
        env_dir.mkdir(exist_ok=True)
        shutil.copy2(TEMPLATE_DIR / "environment" / "Dockerfile", env_dir / "Dockerfile")

        # tests/ (built into the separate verifier image; never in the agent's container)
        tests_dir = task_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        verifier_dockerfile = "Dockerfile.t1" if task.tier == "t1" else "Dockerfile"
        shutil.copy2(TEMPLATE_DIR / "tests" / verifier_dockerfile, tests_dir / "Dockerfile")
        shutil.copy2(TEMPLATE_DIR / "tests" / "test.sh", tests_dir / "test.sh")
        shutil.copy2(TEMPLATE_DIR / "tests" / "judge.py", tests_dir / "judge.py")
        if task.tier == "t1":
            for name in ("t1_ground_truth.py", "market_data.py"):
                shutil.copy2(TEMPLATE_DIR / "tests" / name, tests_dir / name)
        (tests_dir / "task_data.json").write_text(
            json.dumps(task.task_data(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # task.toml
        keywords = json.dumps([DATASET_NAME, task.tier, task.region, "finance"])
        extra_metadata = ""
        if task.tier == "t1":
            # Date label: when the embedded ground truth was fetched (UTC).
            if task.snapshot:
                extra_metadata = (
                    't1_ground_truth = "snapshot, live fallback when not from today (UTC)"\n'
                    f't1_snapshot_date = "{task.snapshot["date"]}"\n'
                    f't1_snapshot_fetched_at = "{task.snapshot["fetched_at"]}"\n'
                )
            else:
                extra_metadata = 't1_ground_truth = "live at grading time"\n'
        task_toml = (TEMPLATE_DIR / "task.toml").read_text(encoding="utf-8")
        task_toml = task_toml.replace("{task_name}", f"{TASK_ORG}/{DATASET_NAME}__{task.id}")
        task_toml = task_toml.replace("{keywords}", keywords)
        task_toml = task_toml.replace("{extra_metadata}\n", extra_metadata)
        task_toml = task_toml.replace(
            "{verifier_timeout_sec}", str(VERIFIER_TIMEOUT_SEC[task.tier])
        )
        (task_dir / "task.toml").write_text(task_toml, encoding="utf-8")

        # instruction.md (the upstream prompt, unchanged, plus an output-location note)
        instruction = (TEMPLATE_DIR / "instruction.md").read_text(encoding="utf-8")
        instruction = instruction.replace("{prompt}", task.prompt)
        (task_dir / "instruction.md").write_text(instruction, encoding="utf-8")

        # solution/ (oracle)
        solution_dir = task_dir / "solution"
        solution_dir.mkdir(exist_ok=True)
        answer = task.oracle_answer()
        if HEREDOC_DELIMITER in answer:
            raise ValueError(f"Heredoc delimiter found in oracle answer for {task.id}")
        solve = (TEMPLATE_DIR / "solution" / "solve.sh").read_text(encoding="utf-8")
        solve = solve.replace("{response_reference}", answer)
        solve_path = solution_dir / "solve.sh"
        solve_path.write_text(solve, encoding="utf-8")
        solve_path.chmod(0o755)
        (tests_dir / "test.sh").chmod(0o755)

    def run(self) -> None:
        self._load_tasks()
        selected = self.tasks
        if self.task_ids is not None:
            wanted = set(self.task_ids)
            selected = [t for t in selected if t.id in wanted or t.prompt_id in wanted]
        if self.limit is not None:
            selected = selected[: self.limit]

        logger.info(
            "Loaded %d questions (%s); generating %d",
            len(self.tasks),
            "+".join(t.upper() for t in self.tiers),
            len(selected),
        )
        self._attach_snapshots(selected)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for task in selected:
            task_dir = self.output_dir / task.id
            if task_dir.exists():
                if not self.overwrite:
                    continue
                shutil.rmtree(task_dir)
            self._prepare_task(task, task_dir)
            self.generated_count += 1
