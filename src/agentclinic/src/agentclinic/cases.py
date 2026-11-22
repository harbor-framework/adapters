import copy
import hashlib
import json
import os
import random
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

UPSTREAM_REPO = "SamuelSchmidgall/AgentClinic"
UPSTREAM_COMMIT = "b6fbe22300e99a267a7ac94eaa465ab552eef741"
DATA_FILE = "agentclinic_medqa_extended.jsonl"
DATA_SHA256 = "d35d276481f3810f0fcb920c72f10b629ec4266d85ce5f8db1ae56467c9a5a34"
DATA_URL = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}/{DATA_FILE}"
TOTAL_CASES = 215
PARITY_SIZE = 22
PARITY_SEED = 42
SPLITS = ("full", "parity")


@dataclass(frozen=True)
class Case:
    index: int
    task_id: str
    objective: str
    patient_actor: dict
    physical_exam: dict
    test_results: dict
    correct_diagnosis: str

    def patient_information(self) -> dict:
        return self.patient_actor

    def examiner_information(self) -> str:
        return self.objective

    def exam_information(self) -> dict:
        exams = copy.deepcopy(self.physical_exam)
        exams["tests"] = self.test_results
        return exams

    def diagnosis_information(self) -> str:
        return self.correct_diagnosis

    def runtime_view(self) -> dict:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "patient_actor": self.patient_actor,
            "physical_exam": self.physical_exam,
            "test_results": self.test_results,
        }


def task_id_for(index: int) -> str:
    return f"medqa-ext-{index:03d}"


def _cache_dir() -> Path:
    root = os.environ.get("AGENTCLINIC_CACHE_DIR")
    base = Path(root) if root else Path.home() / ".cache" / "harbor-agentclinic"
    return base / UPSTREAM_COMMIT


def _download() -> Path:
    target = _cache_dir() / DATA_FILE
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == DATA_SHA256:
        return target
    with urllib.request.urlopen(DATA_URL, timeout=60) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != DATA_SHA256:
        raise RuntimeError(f"{DATA_FILE} sha256 {digest} does not match pinned {DATA_SHA256}")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{DATA_FILE}.")
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
    os.replace(tmp, target)
    return target


def load_cases(source: Path | None = None) -> list[Case]:
    path = Path(source) if source is not None else _download()
    cases = []
    for index, line in enumerate(path.read_text(encoding="utf-8").split("\n")):
        if not line.strip():
            continue
        osce = json.loads(line)["OSCE_Examination"]
        cases.append(
            Case(
                index=index,
                task_id=task_id_for(index),
                objective=osce["Objective_for_Doctor"],
                patient_actor=osce["Patient_Actor"],
                physical_exam=osce["Physical_Examination_Findings"],
                test_results=osce["Test_Results"],
                correct_diagnosis=osce["Correct_Diagnosis"],
            )
        )
    return cases


def parity_indices() -> list[int]:
    return sorted(random.Random(PARITY_SEED).sample(range(TOTAL_CASES), PARITY_SIZE))


def select(
    cases: list[Case],
    split: str = "full",
    task_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[Case]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {SPLITS}")
    chosen = cases
    if split == "parity":
        wanted = set(parity_indices())
        chosen = [c for c in chosen if c.index in wanted]
    if task_ids:
        known = {c.task_id for c in chosen}
        missing = [t for t in task_ids if t not in known]
        if missing:
            raise ValueError(f"unknown task ids for split {split!r}: {', '.join(missing)}")
        wanted_ids = set(task_ids)
        chosen = [c for c in chosen if c.task_id in wanted_ids]
    if limit is not None:
        chosen = chosen[:limit]
    return chosen
