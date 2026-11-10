"""Generate Harbor tasks from the VimGolf-Gym public challenge set.

Source: the 612 vimgolf.com public challenges published by VimGolf-Gym at
https://huggingface.co/datasets/James4Ever0/vimgolf_challenges_and_solutions
(pinned revision below). Each challenge becomes one task whose agent writes a
single-line keystroke solution to /app/solution.txt; a separate verifier sandbox
replays it with the upstream verifier image.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import re
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "task-template"
ORACLE_FILE = Path(__file__).parent / "oracle_solutions.json"

HF_REPO = "James4Ever0/vimgolf_challenges_and_solutions"
HF_REVISION = "5263d1e9df48f0da07c142818dd27363de232823"
HF_ZIP_URL = f"https://huggingface.co/datasets/{HF_REPO}/resolve/{HF_REVISION}/challenges.zip"
HF_ZIP_SHA256 = "dfbb51debdf2e21750969b7a71306e30f0ba411a5ee2499f467e5950e93431c2"


def format_vimgolf(string: str) -> str:
    """vimgolf.vimgolf.format_ (vimgolf==0.5.1): dos2unix and add final newline."""
    string = string.replace("\r\n", "\n").replace("\r", "\n")
    if not string.endswith("\n"):
        string = string + "\n"
    return string


def _sanitize(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-{2,}", "-", text).strip("-")


@dataclass(frozen=True)
class Challenge:
    challenge_id: str
    title: str
    detail: str
    input: str
    output: str
    filetype: str
    public_solution: str | None = None  # worst public solution (oracle candidate only)

    @property
    def task_id(self) -> str:
        # <filetype>-<title>-<challenge id>, the Terminal-Bench adapter's scheme
        # (lowercased because uppercase task names break the registry).
        filetype = _sanitize(self.filetype) or "txt"
        title = _sanitize(self.title) or "untitled"
        return f"{filetype}-{title}-{self.challenge_id.lower()}"


def load_challenges(zip_path: Path | None = None) -> dict[str, Challenge]:
    if zip_path is None:
        LOGGER.info("Downloading %s", HF_ZIP_URL)
        with urllib.request.urlopen(HF_ZIP_URL) as resp:
            data = resp.read()
    else:
        data = Path(zip_path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != HF_ZIP_SHA256:
        raise ValueError(f"challenges.zip sha256 {digest} != pinned {HF_ZIP_SHA256}")

    challenges: dict[str, Challenge] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        ids = sorted(
            {n.split("/")[1] for n in names if n.startswith("challenges/") and n.count("/") >= 2}
            - {""}
        )
        for cid in ids:
            definition = json.loads(zf.read(f"challenges/{cid}/challenge.json"))
            metadata = json.loads(zf.read(f"challenges/{cid}/metadata.json"))
            worst_name = f"challenges/{cid}/worst_solution.json"
            worst = json.loads(zf.read(worst_name)) if worst_name in names else {}
            challenges[cid] = Challenge(
                challenge_id=cid,
                title=metadata["title"],
                detail=metadata["detail"],
                input=definition["in"]["data"],
                output=definition["out"]["data"],
                filetype=definition["in"]["type"] or "",
                public_solution=worst.get("solution"),
            )
    return challenges


def load_oracles(required: bool = True) -> dict[str, dict]:
    if not ORACLE_FILE.is_file():
        if required:
            raise FileNotFoundError(
                f"{ORACLE_FILE} is missing; rebuild it with oracle/build_oracles.py "
                "or pass --include-unverified"
            )
        LOGGER.warning("%s missing; tasks get no oracle solution", ORACLE_FILE)
        return {}
    return json.loads(ORACLE_FILE.read_text())


class VimGolfGymAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        zip_path: Path | None = None,
        include_unverified: bool = False,
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.zip_path = zip_path
        self.include_unverified = include_unverified

    def run(self) -> list[Path]:
        challenges = load_challenges(self.zip_path)
        oracles = load_oracles(required=not self.include_unverified)

        by_task_id = {c.task_id: c for c in challenges.values()}
        if len(by_task_id) != len(challenges):
            raise ValueError("task id collision after sanitization")

        selected = sorted(by_task_id)
        if not self.include_unverified:
            selected = [t for t in selected if by_task_id[t].challenge_id in oracles]
        if self.task_ids:
            wanted = set(self.task_ids)
            # accept either Harbor task ids or raw vimgolf challenge ids
            selected = [
                t for t in selected if t in wanted or by_task_id[t].challenge_id in wanted
            ]
        if self.limit is not None:
            selected = selected[: self.limit]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for task_id in selected:
            challenge = by_task_id[task_id]
            task_dir = self.output_dir / task_id
            if task_dir.exists():
                if not self.overwrite:
                    LOGGER.info("Skipping existing %s", task_id)
                    continue
                shutil.rmtree(task_dir)
            self._write_task(task_dir, challenge, oracles.get(challenge.challenge_id))
            written.append(task_dir)
        LOGGER.info("Wrote %d tasks to %s", len(written), self.output_dir)
        return written

    def _write_task(self, task_dir: Path, c: Challenge, oracle: dict | None) -> None:
        shutil.copytree(TEMPLATE_DIR, task_dir)

        oracle_keys = oracle["keys"] if oracle else ""
        oracle_source = oracle["source"] if oracle else "none"
        title_toml = json.dumps(c.title)[1:-1]

        def render(rel: str, **values: str) -> None:
            path = task_dir / rel
            text = path.read_text()
            for key, value in values.items():
                text = text.replace("{{" + key + "}}", value)
            path.write_text(text)

        render(
            "task.toml",
            TASK_ID=c.task_id,
            CHALLENGE_ID=c.challenge_id,
            TITLE_TOML=title_toml,
            FILETYPE=_sanitize(c.filetype) or "txt",
            KEY_BUDGET=str(len(c.output)),
            ORACLE_SOURCE=oracle_source,
        )
        # upstream prompt uses the raw challenge text (vimgolf-benchmark.py)
        render("instruction.md", DETAILS=c.detail, INPUT=c.input, OUTPUT=c.output)
        render(
            "solution/solve.sh",
            ORACLE_SOURCE=oracle_source,
            ORACLE_KEYS_B64=base64.b64encode(oracle_keys.encode("utf-8")).decode("ascii"),
        )

        env_dir = task_dir / "environment"
        (env_dir / "input.txt").write_text(c.input)
        (env_dir / "output.txt").write_text(c.output)
        (env_dir / "challenge.json").write_text(
            json.dumps(
                {
                    "challenge_id": c.challenge_id,
                    "title": c.title,
                    "detail": c.detail,
                    "input": c.input,
                    "output": c.output,
                },
                indent=2,
            )
        )

        # The verifier only needs the input and the expected output's hash/length.
        (task_dir / "tests" / "grading.json").write_text(
            json.dumps(
                {
                    "challenge_id": c.challenge_id,
                    "input": c.input,
                    "output_sha256": hashlib.sha256(
                        format_vimgolf(c.output).encode("utf-8")
                    ).hexdigest(),
                    "output_len": len(c.output),
                },
                indent=2,
            )
        )
        for script in ("solution/solve.sh", "tests/test.sh"):
            (task_dir / script).chmod(0o755)
