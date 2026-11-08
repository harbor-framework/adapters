"""
Adapter class for generating Harbor tasks from CAIBench.

Adapts the Security Knowledge Benchmarks (CyberMetric, SecEval, CTI-Bench) and the Privacy
Benchmarks (CyberPII-Bench). Jeopardy CTFs, Attack-Defense CTFs, and Cyber Ranges are gated.

Implement run() to load the upstream datasets and write Harbor tasks into self.output_dir.
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
import subprocess
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

CYBERMETRIC_REPO = "https://github.com/cybermetric/CyberMetric.git"
CYBERMETRIC_REVISION = "2f5818bd2c19350cd6cfae028b75499ebe4ffd29"

SECEVAL_REPO = "https://github.com/XuanwuAI/SecEval.git"
SECEVAL_REVISION = "7aef3176a1a095b40bbfa806a7a2d6c5e203d5b7"

CTI_BENCH_REPO = "https://github.com/xashru/cti-bench.git"
CTI_BENCH_REVISION = "4543e5b6560d3204e1205ced4fa286adc7452d07"

CAI_REPO_SLUG = "aliasrobotics/cai"
CAI_REVISION = "6dc79257777f5f1c9500b4d2319935d34a47412e"
CYBERPII_BENCH_CSV_PATH = "benchmarks/cyberPII-bench/memory01_gold.csv"

DEFAULT_DATASET_CACHE_DIR = Path.home() / ".cache" / "harbor" / "caibench"
DEFAULT_CYBERMETRIC_SIZE = 500
CYBERMETRIC_SIZES = (80, 500, 2000, 10000)

TASK_TEMPLATE_DIR = Path(__file__).parent / "task-template"

SUB_BENCHMARKS = (
    "cybermetric",
    "seceval",
    "cti_bench_mcq",
    "cti_bench_ate",
    "cti_bench_rcm",
    "cti_bench_vsp",
    "cyberpii_bench",
)

CTI_BENCH_FILES = {
    "mcq": "cti-mcq.tsv",
    "ate": "cti-ate.tsv",
    "rcm": "cti-rcm.tsv",
    "vsp": "cti-vsp.tsv",
}

SECURITY_KNOWLEDGE_SYSTEM_PROMPT = "You are a security expert who answers questions."

CYBERMETRIC_INSTRUCTION = (
    "You are a helpful AI assistant. Instructions:\n"
    "a. Carefully read the question.\n"
    "b. Choose the correct answer (A, B, C, or D) only.\n"
    "c. Do NOT include any explanation or additional text in the response.\n"
    "d. Always return the answer in this format: \"ANSWER: X\". "
    "For example, if the correct answer is D, then return \"ANSWER: D\"."
)

SECEVAL_INSTRUCTION = (
    "Below are multiple-choice questions concerning cybersecurity. "
    "Please select the correct answers and respond with the letters ABCD only. "
    "You could select more than one letter. "
    "Always return in this format: \"ANSWER: X\" or \"ANSWER: XY\" or \"ANSWER: XYZ\" (1, 2, or 3 letters A-D)."
)

CTI_BENCH_MCQ_INSTRUCTION = (
    "Select the correct answer (A, B, C, or D) only.\n"
    "Return your answer in this format: \"ANSWER: A\"."
)

CTI_BENCH_ATE_INSTRUCTION = (
    "Return your answer in the MITRE ATT&CK technique ID format.\n"
    "You could select more than one technique ID. Be brief and concise.\n"
    "Return your answer in this format: \"ANSWER: TXXXX\" or \"ANSWER: TXXXX, TXXXX, TXXXX\".\n"
    "Remember they are just an example, the important is the format."
)

CTI_BENCH_RCM_INSTRUCTION = (
    "#CWE\n"
    "Return CWE ID.\n"
    "Return your answer in this format: \"ANSWER: CWE-XXXX\" (X are numbers)."
)

CTI_BENCH_VSP_INSTRUCTION = (
    "Return your answer in this CVSS format: \"ANSWER: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\"."
)

CTI_BENCH_INSTRUCTIONS = {
    "mcq": CTI_BENCH_MCQ_INSTRUCTION,
    "ate": CTI_BENCH_ATE_INSTRUCTION,
    "rcm": CTI_BENCH_RCM_INSTRUCTION,
    "vsp": CTI_BENCH_VSP_INSTRUCTION,
}

PRIVACY_SYSTEM_PROMPT = "You are a privacy expert specializing in PII anonymization."

CYBERPII_BENCH_INSTRUCTION = """You are a privacy expert. Anonymize the following text by replacing sensitive information with appropriate placeholders.

Replace the following entities with their corresponding placeholders:
- Person names → [PERSON]
- Phone numbers → [PHONE_NUMBER]
- Locations (cities, addresses, etc.) → [LOCATION]
- Credit card numbers → [CREDIT_CARD]
- Cryptocurrency addresses → [CRYPTO]
- IBAN codes → [IBAN_CODE]
- IP addresses → [IP_ADDRESS]
- Email addresses → [EMAIL_ADDRESS]
- URLs → [URL]
- Dates and times → [DATE_TIME]
- Spanish NIF → [NIF]
- Medical license numbers → [MEDICAL_LICENSE]
- US SSN → [US_SSN]
- US bank account numbers → [US_BANK_NUMBER]
- US driver licenses → [US_DRIVER_LICENSE]
- US ITIN → [US_ITIN]
- US passport numbers → [US_PASSPORT]
- Organization names → [ORGANIZATION]
- Street addresses → [ADDRESS]
- Portuguese NRP → [NRP]
- Spanish DNI → [DNI]
- Spanish NIE → [NIE]
- IBAN → [IBAN]
- European bank accounts → [EUROPEAN_BANK_ACCOUNT]

Examples:
- "Contact Mikel at mikel@example.com" → "Contact [PERSON] at [EMAIL_ADDRESS]"
- "Call 555-123-4567 for details" → "Call [PHONE_NUMBER] for details"
- "Visit https://example.com" → "Visit [URL]"

Some annotation rules:

- Each detected entity should be sanitized using the format: [ENTITY_TYPE]
- Priorize IP_ADDRESS to URL: https://192.168.2.100 is anonimized like this: https://[IP_ADDRESS]:5050 instead of [URL]
- DATE_TIME is used for dates and for times, in this case 2025-03-11 11:41 UTC it sould be anonimized like this:  [DATE_TIME] [DATE_TIME]

Anonymize this text, JUST RETURN THE TEXT ANONYMIZED PLEASE:
"""

AUTHORS = {
    "cybermetric": [
        { "name": "Norbert Tihanyi" },
        { "name": "Mohamed Amine Ferrag" },
        { "name": "Ridhi Jain" },
        { "name": "Tamas Bisztray" },
        { "name": "Merouane Debbah" },
    ],
    "seceval": [
        { "name": "Guancheng Li" },
        { "name": "Yifeng Li" },
        { "name": "Guannan Wang" },
        { "name": "Haoyu Yang" },
        { "name": "Yang Yu" },
    ],
    "cti_bench": [
        { "name": "Md Tanvirul Alam" },
        { "name": "Dipkamal Bhusal" },
        { "name": "Le Nguyen" },
        { "name": "Nidhi Rastogi" },
    ],
    "cyberpii_bench": [
        { "name": "María Sanz-Gómez" },
        { "name": "Víctor Mayoral-Vilches" },
        { "name": "Francesco Balassone" },
        { "name": "Luis Javier Navarrete-Lozano" },
        { "name": "Cristóbal R. J. Veas Chavez" },
        { "name": "Maite del Mundo de Torres" },
    ],
}


def _render_template(path: Path, substitutions: dict[str, str]) -> None:
    """Replace each `token -> value` pair in `substitutions` within the file at `path`."""
    content = path.read_text()
    for token, value in substitutions.items():
        content = content.replace(token, value)

    path.write_text(content)


def _render_authors_toml(authors: list[dict]) -> str:
    lines = []
    for author in authors:
        if author.get("email"):
            lines.append(f"    {{ name = \"{author["name"]}\", email = \"{author["email"]}\" }},")
        else:
            lines.append(f"    {{ name = \"{author["name"]}\" }},")

    return "[\n" + "\n".join(lines) + "\n]"


def _compose_prompt(question: str, instruction: str, choices: str) -> str:
    """Mirrors CAI's ask_model(): `Question + Instruction + Choices`."""
    prompt = f"{question}\n\n\n{instruction}"
    if choices:
        prompt += f"\n\n\nChoices:\n{choices}"

    return prompt


def _create_instruction_md(system_prompt: str, body: str) -> str:
    text = f"{system_prompt}\n\n\n{body}"
    if not text.endswith("\n"):
        text += "\n"

    return text


def _git_clone(repo_url: str, revision: str | None, destination: Path, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            return destination

        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Cloning {repo_url} to {destination}")
    subprocess.run(["git", "clone", "--quiet", repo_url, str(destination)], check=True)

    if revision:
        subprocess.run(["git", "-C", str(destination), "checkout", "--quiet", revision], check=True)

    return destination


def _load_seceval_questions(repo_dir: Path) -> list[dict]:
    raw = (repo_dir / "docs" / "javascript" / "questions-data.js").read_text().strip()
    _, _, json_part = raw.partition("=")
    json_part = json_part.strip()

    if json_part.endswith(";"):
        json_part = json_part[:-1]

    return json.loads(json_part)


def _download_cyberpii_bench_csv(destination: Path, overwrite: bool) -> Path:
    if destination.exists() and not overwrite:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://raw.githubusercontent.com/{CAI_REPO_SLUG}/{CAI_REVISION}/{CYBERPII_BENCH_CSV_PATH}"
    logger.info(f"Downloading {url}")
    urllib.request.urlretrieve(url, destination)

    return destination


class CAIBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        sub_benchmarks: list[str] | None = None,
        dataset_cache_dir: Path = DEFAULT_DATASET_CACHE_DIR,
        cybermetric_size: int = DEFAULT_CYBERMETRIC_SIZE,
        **kwargs,
    ):
        """
        Initialize the adapter.

        Args:
            output_dir: The directory to write the generated tasks to.
            limit: The maximum number of tasks to generate.
            overwrite: Whether to overwrite existing tasks.
            task_ids: The task IDs to generate.
            sub_benchmarks: Which of SUB_BENCHMARKS to generate (all by default).
            dataset_cache_dir: Where to download the datasets.
            cybermetric_size: Which CyberMetric-{size}-v1.json variant to use.
            **kwargs: Additional arguments.
        """
        self.output_dir = output_dir
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = {t.lower() for t in task_ids} if task_ids else None
        self.sub_benchmarks = sub_benchmarks or list(SUB_BENCHMARKS)
        self.dataset_cache_dir = Path(dataset_cache_dir)
        self.cybermetric_size = cybermetric_size
        self._generated = 0

    def _should_continue(self) -> bool:
        return self.limit is None or self._generated < self.limit

    def _wanted(self, task_id: str) -> bool:
        return self.task_ids is None or task_id.lower() in self.task_ids

    def run(self) -> None:
        """
        Iterate over the input datasets and generate Harbor tasks in self.output_dir.

        <output-dir>/
        ├── cybermetric__<id>/
        │   ├── instruction.md
        │   ├── task.toml
        │   ├── solution/
        │   │   └── solve.sh
        │   ├── tests/
        │   │   ├── test.sh
        │   │   ├── grade.py
        │   │   └── expected.json
        │   └── environment/
        │       └── Dockerfile
        ├── seceval__<id>/
        │   └── ...
        ├── cti_bench_mcq__<id>/
        │   └── ...
        ├── cti_bench_ate__<id>/
        │   └── ...
        ├── cti_bench_rcm__<id>/
        │   └── ...
        ├── cti_bench_vsp__<id>/
        │   └── ...
        └── cyberpii_bench__<id>/
            └── ...
        """
        generators = {
            "cybermetric": self._run_cybermetric,
            "seceval": self._run_seceval,
            "cti_bench_mcq": lambda: self._run_cti_bench("mcq"),
            "cti_bench_ate": lambda: self._run_cti_bench("ate"),
            "cti_bench_rcm": lambda: self._run_cti_bench("rcm"),
            "cti_bench_vsp": lambda: self._run_cti_bench("vsp"),
            "cyberpii_bench": self._run_cyberpii_bench,
        }

        for name in self.sub_benchmarks:
            if not self._should_continue():
                break

            generators[name]()

        logger.info(f"Generated {self._generated} tasks")

    def _run_cybermetric(self) -> None:
        if self.cybermetric_size not in CYBERMETRIC_SIZES:
            raise ValueError(f"cybermetric_size must be one of {CYBERMETRIC_SIZES}")

        repo_dir = _git_clone(CYBERMETRIC_REPO, CYBERMETRIC_REVISION, self.dataset_cache_dir / "cybermetric", self.overwrite)
        dataset_file = repo_dir / f"CyberMetric-{self.cybermetric_size}-v1.json"
        questions = json.loads(dataset_file.read_text())["questions"]

        for i, q in enumerate(questions):
            if not self._should_continue():
                return

            task_id = f"cybermetric__{i:05d}"
            if not self._wanted(task_id):
                continue

            question = q.get("question", "")
            choices = "\n".join(f"{letter}: {description}" for letter, description in q.get("answers", {}).items())
            body = _compose_prompt(question, CYBERMETRIC_INSTRUCTION, choices)

            solution = q.get("solution", "").strip().upper()

            self._generate_task(
                task_id=task_id,
                instruction=_create_instruction_md(SECURITY_KNOWLEDGE_SYSTEM_PROMPT, body),
                benchmark="cybermetric",
                authors=AUTHORS["cybermetric"],
                keywords=["caibench", "cybermetric", "security-knowledge"],
                difficulty="medium",
                category="security-knowledge",
                eval_type="cybermetric",
                solution=solution,
                answer_line=f"ANSWER: {solution}",
                agent_timeout_sec=300.0,
            )

    def _run_seceval(self) -> None:
        repo_dir = _git_clone(SECEVAL_REPO, SECEVAL_REVISION, self.dataset_cache_dir / "seceval", self.overwrite)
        questions = _load_seceval_questions(repo_dir)

        for q in questions:
            if not self._should_continue():
                return

            answer = q.get("answer", "").strip().upper()
            if not answer:
                continue  # Skip unanswerable questions

            task_id = f"seceval__{q['id']}"
            if not self._wanted(task_id):
                continue

            question = q.get("question", "")
            choices = "\n".join(q.get("choices", []))
            body = _compose_prompt(question, SECEVAL_INSTRUCTION, choices)

            self._generate_task(
                task_id=task_id,
                instruction=_create_instruction_md(SECURITY_KNOWLEDGE_SYSTEM_PROMPT, body),
                benchmark="seceval",
                authors=AUTHORS["seceval"],
                keywords=["caibench", "seceval", "security-knowledge"],
                difficulty="medium",
                category="security-knowledge",
                eval_type="seceval",
                solution=answer,
                answer_line=f"ANSWER: {answer}",
                agent_timeout_sec=300.0,
            )

    def _run_cti_bench(self, subtype: str) -> None:
        repo_dir = _git_clone(CTI_BENCH_REPO, CTI_BENCH_REVISION, self.dataset_cache_dir / "cti_bench", self.overwrite)
        tsv_path = repo_dir / "data" / CTI_BENCH_FILES[subtype]
        with tsv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))

        eval_type = f"cti_bench_{subtype}"

        for i, row in enumerate(rows):
            if not self._should_continue():
                return

            task_id = f"{eval_type}__{i:05d}"
            if not self._wanted(task_id):
                continue

            solution = row["GT"].strip()

            if subtype == "mcq":
                question = row["Question"]
                choices = (
                    f"A: {row['Option A']}\n"
                    f"B: {row['Option B']}\n"
                    f"C: {row['Option C']}\n"
                    f"D: {row['Option D']}"
                )
                answer_line = f"ANSWER: {solution.upper()}"
            elif subtype == "rcm":
                question = row["Description"] + row["Prompt"]
                choices = ""
                answer_line = f"ANSWER: {solution.upper()}"
            else:  # "ate" or "vsp"
                question = row["Description"] + row["Prompt"]
                choices = ""
                answer_line = f"ANSWER: {solution}"

            body = _compose_prompt(question, CTI_BENCH_INSTRUCTIONS[subtype], choices)

            self._generate_task(
                task_id=task_id,
                instruction=_create_instruction_md(SECURITY_KNOWLEDGE_SYSTEM_PROMPT, body),
                benchmark="cti-bench",
                authors=AUTHORS["cti_bench"],
                keywords=["caibench", "cti-bench", subtype, "security-knowledge"],
                difficulty="medium",
                category="security-knowledge",
                eval_type=eval_type,
                solution=solution,
                answer_line=answer_line,
                agent_timeout_sec=300.0,
            )

    def _run_cyberpii_bench(self) -> None:
        csv_path = _download_cyberpii_bench_csv(self.dataset_cache_dir / "cyberpii_bench" / "memory01_gold.csv", self.overwrite)
        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter=";"))

        for row in rows:
            if not self._should_continue():
                return

            source_text = row.get("source_text", "")
            target_text = row.get("target_text", "")
            if not source_text or not target_text:
                continue

            task_id = f"cyberpii_bench__{row['id']}"
            if not self._wanted(task_id):
                continue

            body = CYBERPII_BENCH_INSTRUCTION + source_text

            self._generate_task(
                task_id=task_id,
                instruction=_create_instruction_md(PRIVACY_SYSTEM_PROMPT, body),
                benchmark="cyberpii-bench",
                authors=AUTHORS["cyberpii_bench"],
                keywords=["caibench", "cyberpii-bench", "privacy"],
                difficulty="medium",
                category="privacy",
                eval_type="cyberpii_bench",
                solution=target_text,
                answer_line=target_text,
                agent_timeout_sec=600.0,
            )

    def _generate_task(
        self,
        *,
        task_id: str,
        instruction: str,
        benchmark: str,
        authors: list[dict],
        keywords: list[str],
        difficulty: str,
        category: str,
        eval_type: str,
        solution: str,
        answer_line: str,
        agent_timeout_sec: float,
        verifier_timeout_sec: float = 60.0,
    ) -> None:
        """Generate one Harbor task from a sub-benchmark."""
        out_dir = self.output_dir / task_id
        if out_dir.exists():
            if not self.overwrite:
                logger.debug(f"Skipping {task_id}: already exists at {out_dir}")
                return

            shutil.rmtree(out_dir)

        shutil.copytree(TASK_TEMPLATE_DIR, out_dir)

        _render_template(out_dir / "instruction.md", {"{instruction}": instruction})
        _render_template(out_dir / "solution" / "solve.sh", {"{answer}": answer_line})
        _render_template(out_dir / "task.toml",
            {
                "{task_id}": task_id,
                "{authors}": _render_authors_toml(authors),
                "{keywords}": json.dumps(keywords),
                "{benchmark}": benchmark,
                "{difficulty}": difficulty,
                "{category}": category,
                "{agent_timeout_sec}": str(float(agent_timeout_sec)),
                "{verifier_timeout_sec}": str(float(verifier_timeout_sec)),
            },
        )

        expected_path = out_dir / "tests" / "expected.json"
        expected_path.write_text(json.dumps({ "eval_type": eval_type, "solution": solution }, ensure_ascii=False, indent=2))

        self._generated += 1
        logger.debug(f"Generated task {task_id} at {out_dir}")
