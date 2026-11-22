import json
import shutil
from pathlib import Path

from . import prompts
from .cases import Case, load_cases, parity_indices, select, task_id_for

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "task-template"
RUNTIME_MODULES = ("prompts.py", "clinic.py", "llm.py")
VERIFIER_MODULES = ("prompts.py", "llm.py")


class AgentClinicAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        source: Path | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split
        self.source = source

    def run(self) -> list[Path]:
        cases = select(load_cases(self.source), split=self.split, task_ids=self.task_ids, limit=self.limit)
        if self.split == "parity":
            self._refuse_foreign_tasks({task_id_for(i) for i in parity_indices()})
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for case in cases:
            task_dir = self.output_dir / case.task_id
            if task_dir.exists():
                if not self.overwrite:
                    print(f"skip {case.task_id}: exists (use --overwrite)")
                    written.append(task_dir)
                    continue
                shutil.rmtree(task_dir)
            self._write_task(case, task_dir)
            written.append(task_dir)
        print(f"wrote {len(written)} tasks to {self.output_dir}")
        return written

    def _refuse_foreign_tasks(self, allowed: set[str]) -> None:
        if not self.output_dir.exists():
            return
        foreign = sorted(
            p.name for p in self.output_dir.iterdir() if (p / "task.toml").exists() and p.name not in allowed
        )
        if foreign:
            raise ValueError(
                f"{self.output_dir} holds tasks outside the parity split ({', '.join(foreign[:5])}"
                f"{', ...' if len(foreign) > 5 else ''}); use an empty directory for --split parity"
            )

    def _write_task(self, case: Case, task_dir: Path) -> None:
        shutil.copytree(TEMPLATE_DIR, task_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self._render(task_dir / "task.toml", {"{task_id}": case.task_id})
        doctor_prompt = prompts.doctor_system_prompt(prompts.MAX_INFERENCES, 0, case.examiner_information())
        self._render(task_dir / "instruction.md", {"{doctor_prompt}": doctor_prompt})
        self._render(task_dir / "solution" / "solve.sh", {"{diagnosis_json}": json.dumps(case.correct_diagnosis)})
        runtime = task_dir / "environment" / "runtime"
        for module in RUNTIME_MODULES:
            shutil.copy(PACKAGE_DIR / module, runtime / module)
        (runtime / "case.json").write_text(
            json.dumps(case.runtime_view(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tests = task_dir / "tests"
        for module in VERIFIER_MODULES:
            shutil.copy(PACKAGE_DIR / module, tests / module)
        verifier_case = {"task_id": case.task_id, "correct_diagnosis": case.correct_diagnosis}
        (tests / "case.json").write_text(json.dumps(verifier_case, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _render(path: Path, values: dict[str, str]) -> None:
        text = path.read_text(encoding="utf-8")
        for token, value in values.items():
            if token not in text:
                raise ValueError(f"{path.name} has no {token} placeholder")
            text = text.replace(token, value)
        path.write_text(text, encoding="utf-8")
