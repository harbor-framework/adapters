"""AxionLimitBench adapter: one Harbor task per gradable paper.

Each task gives the agent one physics paper (PDF) and the benchmark's task
card. The agent writes ``/app/result.json`` with the paper's exclusion limit
as a curve in a canonical (mass, coupling) plane. A separate verifier grades
that file with the benchmark's own scorer.

Generation needs a checkout of the benchmark at the pinned commit. The
adapter clones it into a cache directory unless ``repo_dir`` is given.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

UPSTREAM_REPO = "https://github.com/FaroutYLq/AxionLimitBench"
UPSTREAM_COMMIT = "08e634dacf9e98632b6faa1c21338fb77294b83f"  # tag v0.1.3
CACHE_DIR = Path.home() / ".cache" / "axionlimitbench-adapter"

TEMPLATE_DIR = Path(__file__).parent / "task-template"
PDF_PINS_FILE = Path(__file__).parent / "pdf_pins.json"
PARITY_TASK_IDS_FILE = Path(__file__).parent / "parity_task_ids.txt"
SPLITS = ("full", "parity")

TAU = math.log10(1.1)  # the benchmark's success tolerance: within 10 percent
MAX_ORACLE_POINTS = 5000
DEFAULT_VERIFIER_TIMEOUT_SEC = 600.0
LARGE_REFERENCE_POINTS = 20000
LARGE_VERIFIER_TIMEOUT_SEC = 3600.0

# The `coupling_convention` label the task card requires for each coupling.
CANONICAL_LABEL = {
    "AxionPhoton": "g_agamma [GeV^-1]",
    "AxionElectron": "g_ae (dimensionless)",
    "AxionNeutron": "g_an (dimensionless)",
    "AxionProton": "g_ap (dimensionless)",
    "AxionEDM": "g_d [GeV^-2]",
    "AxionMass": "1/f_a [GeV^-1]",
    "DarkPhoton": "kinetic mixing chi (dimensionless)",
    "VectorBL": "g_BL (dimensionless)",
    "ScalarPhoton": "d_e (dimensionless)",
    "ScalarElectron": "d_me (dimensionless)",
    "ScalarNucleon": "coupling (dimensionless)",
    "ScalarBaryon": "coupling (dimensionless)",
    "MonopoleDipole": "g_s g_p (dimensionless)",
    "AxionCPV": "coupling (dimensionless)",
}

# Papers the benchmark lists as scorable but whose reference cannot grade any
# answer: the scorer returns the given status for every submission, and the
# benchmark's leaderboard removes such papers from its denominator.
UNGRADEABLE = {
    "2312.11608": "excluded_gt",
    "2402.00741": "gt_unusable",
    "2504.16044": "gt_unusable",
}


@dataclass
class PaperTask:
    arxiv_id: str
    name: str
    coupling_type: str
    oracle: dict
    oracle_how: str
    oracle_residual_dex: float
    reference_points: int
    entries: list[dict] = field(default_factory=list)


def task_name(arxiv_id: str) -> str:
    """`2208.07293` -> `2208-07293`, `hep-ph/0307284` -> `hep-ph-0307284`."""
    return arxiv_id.lower().replace("/", "-").replace(".", "-")


def _thin(points: list[list[float]], limit: int = MAX_ORACLE_POINTS) -> list[list[float]]:
    if len(points) <= limit:
        return points
    step = math.ceil(len(points) / limit)
    out = points[::step]
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def _envelope(points: list[list[float]], upper: bool, bins: int = 200) -> list[list[float]]:
    """One boundary branch of a reference stored as a closed contour."""
    logs = [math.log10(p[0]) for p in points]
    lo, hi = min(logs), max(logs)
    if hi <= lo:
        return points
    best: dict[int, list[float]] = {}
    for (x, y), lx in zip(points, logs):
        b = min(bins - 1, int((lx - lo) / (hi - lo) * bins))
        if b not in best or (y > best[b][1] if upper else y < best[b][1]):
            best[b] = [x, y]
    return sorted(best.values())


class AxionLimitBenchAdapter:
    """Converts AxionLimitBench papers into Harbor task directories."""

    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        repo_dir: Path | None = None,
    ):
        if split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split
        self.repo_dir = Path(repo_dir) if repo_dir else None
        self._ev = None
        self._entries_by_paper: dict[str, list] = {}

    # ------------------------------------------------------------------ source

    def _ensure_repo(self) -> Path:
        if self.repo_dir is not None:
            repo = self.repo_dir.resolve()
            if not (repo / "data" / "manifest.json").is_file():
                raise FileNotFoundError(f"{repo} is not an AxionLimitBench checkout")
            head = self._git(repo, "rev-parse", "HEAD", check=False)
            if head and head != UPSTREAM_COMMIT:
                raise RuntimeError(
                    f"{repo} is at commit {head}, but the adapter is pinned to {UPSTREAM_COMMIT}"
                )
            if not head:
                logger.warning("%s is not a git checkout; its revision cannot be verified", repo)
            return repo

        repo = CACHE_DIR / f"AxionLimitBench-{UPSTREAM_COMMIT[:12]}"
        if (repo / "data" / "manifest.json").is_file():
            if self._git(repo, "rev-parse", "HEAD", check=False) == UPSTREAM_COMMIT:
                return repo
            shutil.rmtree(repo)
        repo.mkdir(parents=True, exist_ok=True)
        logger.info("Fetching %s at %s", UPSTREAM_REPO, UPSTREAM_COMMIT)
        try:
            self._git(repo, "init", "-q")
            self._git(repo, "remote", "add", "origin", UPSTREAM_REPO)
            self._git(repo, "fetch", "-q", "--depth", "1", "origin", UPSTREAM_COMMIT)
            self._git(repo, "checkout", "-q", "FETCH_HEAD")
        except (subprocess.CalledProcessError, OSError) as exc:
            shutil.rmtree(repo, ignore_errors=True)
            raise RuntimeError(
                f"Could not fetch {UPSTREAM_REPO} at {UPSTREAM_COMMIT}: {exc}. "
                "Clone it yourself and pass --repo-dir."
            ) from exc
        return repo

    @staticmethod
    def _git(repo: Path, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    def _load_scorer(self, repo: Path) -> None:
        """Import the benchmark's scorer from the checkout."""
        os.environ["AAL_EXCLUDE_PROJECTIONS"] = "1"
        sys.path.insert(0, str(repo))
        import scorer.evaluate as ev
        from scorer.ground_truth import load_ground_truth

        if Path(ev.__file__).resolve().parent.parent != repo.resolve():
            raise RuntimeError("A different `scorer` package is already imported")
        self._ev = ev
        for entry in load_ground_truth():
            if not entry.is_projection:
                self._entries_by_paper.setdefault(entry.arxiv_id, []).append(entry)

    # ------------------------------------------------------------------ oracle

    def _grade(self, arxiv_id: str, prediction: dict) -> tuple[str | None, float]:
        entries = self._entries_by_paper[arxiv_id]
        metrics = self._ev.compute_all_metrics(entries, [prediction] * len(entries))
        rows = [p for p in metrics.get("per_paper") or [] if p.get("arxiv_id") == arxiv_id]
        if len(rows) != 1:
            raise RuntimeError(f"expected one scored row for {arxiv_id}, got {len(rows)}")
        row = rows[0]
        status = row.get("comparison_status")
        if status is None and row.get("status") == "excluded_gt":
            status = "excluded_gt"
        try:
            residual = float((row.get("interp_metrics") or {}).get("median_residual_dex"))
        except (TypeError, ValueError):
            residual = float("nan")
        return status, residual

    def _build_oracle(self, arxiv_id: str) -> tuple[PaperTask | None, str | None]:
        """Reference curve in the canonical plane, checked with the scorer.

        Returns ``(task, None)`` or ``(None, status)`` when no answer can be
        graded for this paper.
        """
        import numpy as np
        from scorer.conventions import file_source_convention

        ev = self._ev
        last_status: str | None = "excluded_gt"
        for entry in self._entries_by_paper.get(arxiv_id, []):
            if entry.excluded:
                continue
            data = entry.load_data()
            if data is None:
                continue
            coupling = ev._authoritative_coupling(entry)
            curve, _ = ev._canonicalize_curve(
                coupling,
                np.array(data, dtype=float, ndmin=2),
                file_source_convention(entry.reference_repo_file, coupling),
            )
            full = [
                [float(x), float(y)]
                for x, y in curve
                if x > 0 and y > 0 and math.isfinite(x) and math.isfinite(y)
            ]
            if not full:
                continue
            candidates = [("full", full)] if len(full) <= MAX_ORACLE_POINTS else [("thinned", _thin(full))]
            candidates.append(("upper_envelope", _envelope(_thin(full), upper=True)))
            candidates.append(("lower_envelope", _envelope(_thin(full), upper=False)))
            if len(full) > MAX_ORACLE_POINTS:
                # Last resort for a dense, noisy reference that no reduced curve
                # reproduces within the tolerance: keep every vertex.
                candidates.append(("full_resolution", full))
            for how, points in candidates:
                oracle = {
                    "paper_title": entry.paper_title,
                    "coupling_type": coupling,
                    "is_new_limit": True,
                    "is_projection": False,
                    "data_points": points,
                    "data_source": "none",
                    "dm_density_assumed": entry.dm_density_assumed,
                    "confidence_level": entry.confidence_level,
                    "coupling_convention": CANONICAL_LABEL[coupling],
                    "suggested_experiment_name": None,
                    "extraction_confidence": 1.0,
                    "notes": "Reference curve in the canonical plane.",
                }
                status, residual = self._grade(arxiv_id, {**oracle, "arxiv_id": arxiv_id})
                last_status = status
                if status == "compared" and math.isfinite(residual) and residual <= TAU:
                    return (
                        PaperTask(
                            arxiv_id=arxiv_id,
                            name=task_name(arxiv_id),
                            coupling_type=coupling,
                            oracle=oracle,
                            oracle_how=how,
                            oracle_residual_dex=residual,
                            reference_points=len(full),
                        ),
                        None,
                    )
        return None, last_status

    # ------------------------------------------------------------------- tasks

    def _load_parity_names(self) -> list[str]:
        try:
            lines = PARITY_TASK_IDS_FILE.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Cannot read parity task list {PARITY_TASK_IDS_FILE}: {exc}") from exc
        return [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    def _select(self, scorable: list[str]) -> list[str]:
        ids = list(scorable)
        if self.split == "parity":
            wanted = set(self._load_parity_names())
            unknown = wanted - {task_name(i) for i in ids}
            if unknown:
                raise ValueError(f"Parity task list names unknown tasks: {sorted(unknown)}")
            ids = [i for i in ids if task_name(i) in wanted]
        if self.task_ids:
            wanted = {t.lower() for t in self.task_ids}
            ids = [i for i in ids if i.lower() in wanted or task_name(i) in wanted]
            if not ids:
                raise ValueError(f"No task matches --task-ids {self.task_ids}")
        return ids

    def run(self) -> None:
        repo = self._ensure_repo()
        self._load_scorer(repo)
        try:
            pins = json.loads(PDF_PINS_FILE.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RuntimeError(f"Cannot read PDF pin table {PDF_PINS_FILE}: {exc}") from exc
        manifest = json.loads((repo / "data" / "manifest.json").read_text(encoding="utf-8"))
        papers_json = json.loads((repo / "data" / "papers.json").read_text(encoding="utf-8"))
        task_card = self._task_card(repo)

        scorable = [p["arxiv_id"] for p in manifest["papers"] if p["scorable"]]
        selected = self._select(scorable)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        skipped: dict[str, str] = {}
        for arxiv_id in selected:
            if self.limit is not None and written >= self.limit:
                break
            # Building an oracle grades it with the scorer, which takes minutes
            # for the largest references. Skip existing tasks before that.
            if not self.overwrite and (self.output_dir / task_name(arxiv_id)).exists():
                logger.info("Skipping existing task %s", task_name(arxiv_id))
                continue
            task, status = self._build_oracle(arxiv_id)
            if task is None:
                if UNGRADEABLE.get(arxiv_id) != status:
                    raise RuntimeError(
                        f"{arxiv_id}: no reference answer passes the scorer (status {status!r}) "
                        "and the paper is not in the documented ungradeable list"
                    )
                skipped[arxiv_id] = str(status)
                continue
            if arxiv_id in UNGRADEABLE:
                raise RuntimeError(f"{arxiv_id} is listed as ungradeable but an answer passed")
            if arxiv_id not in pins:
                raise RuntimeError(f"{arxiv_id} has no entry in the PDF pin table")
            task_dir = self.output_dir / task.name
            if task_dir.exists():
                if not self.overwrite:
                    logger.info("Skipping existing task %s", task.name)
                    continue
                shutil.rmtree(task_dir)
            self._write_task(task, task_dir, repo, pins[arxiv_id], papers_json, task_card)
            written += 1

        logger.info("Generated %d tasks in %s", written, self.output_dir)
        for arxiv_id, status in skipped.items():
            logger.info("Not generated (ungradeable, scorer status %s): %s", status, arxiv_id)

    @staticmethod
    def _task_card(repo: Path) -> str:
        lines = (repo / "docs" / "TASK.md").read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("# "):
            raise RuntimeError("Unexpected task card format")
        # The first line names the benchmark; the agent should not be told.
        lines[0] = "# Task card"
        card = "\n".join(lines).strip()
        if "AxionLimitBench" in card:
            raise RuntimeError("The task card still names the benchmark")
        return card

    def _write_task(
        self,
        task: PaperTask,
        task_dir: Path,
        repo: Path,
        pin: dict,
        papers_json: dict,
        task_card: str,
    ) -> None:
        (task_dir / "environment").mkdir(parents=True)
        (task_dir / "solution").mkdir()
        tests = task_dir / "tests"
        (tests / "data" / "ground_truth").mkdir(parents=True)

        def render(name: str, **values: str) -> str:
            text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
            for key, value in values.items():
                text = text.replace("{" + key + "}", value)
            return text

        timeout = (
            LARGE_VERIFIER_TIMEOUT_SEC
            if task.reference_points > LARGE_REFERENCE_POINTS
            else DEFAULT_VERIFIER_TIMEOUT_SEC
        )
        (task_dir / "task.toml").write_text(
            render(
                "task.toml",
                task_name=task.name,
                coupling_slug=task.coupling_type.lower(),
                arxiv_id=task.arxiv_id,
                arxiv_version=pin["version"],
                coupling_type=task.coupling_type,
                upstream_code_revision=UPSTREAM_COMMIT,
                verifier_timeout_sec=str(timeout),
            ),
            encoding="utf-8",
        )
        (task_dir / "instruction.md").write_text(
            render("instruction.md", arxiv_id=task.arxiv_id, task_card=task_card),
            encoding="utf-8",
        )
        (task_dir / "environment" / "Dockerfile").write_text(
            render("environment/Dockerfile", pdf_url=pin["url"], pdf_sha256=pin["sha256"]),
            encoding="utf-8",
        )

        solve = task_dir / "solution" / "solve.sh"
        shutil.copy2(TEMPLATE_DIR / "solution" / "solve.sh", solve)
        solve.chmod(0o755)
        (task_dir / "solution" / "result.json").write_text(
            json.dumps(task.oracle, indent=1), encoding="utf-8"
        )

        for name in ("Dockerfile", "test.sh", "score.py"):
            shutil.copy2(TEMPLATE_DIR / "tests" / name, tests / name)
        (tests / "test.sh").chmod(0o755)
        shutil.copytree(
            repo / "scorer",
            tests / "scorer",
            ignore=shutil.ignore_patterns("__pycache__", "tests", "*.pyc"),
        )
        entries = [e for e in papers_json["papers"] if e.get("arxiv_id") == task.arxiv_id]
        (tests / "data" / "papers.json").write_text(
            json.dumps({**{k: v for k, v in papers_json.items() if k != "papers"}, "papers": entries}, indent=1),
            encoding="utf-8",
        )
        for entry in entries:
            name = entry.get("ground_truth_data_file")
            source = repo / "data" / "ground_truth" / name if name else None
            if source is not None and source.is_file():
                shutil.copy2(source, tests / "data" / "ground_truth" / name)
        (tests / "task.json").write_text(
            json.dumps(
                {
                    "arxiv_id": task.arxiv_id,
                    "reference_coupling_type": task.coupling_type,
                    "reference_points": task.reference_points,
                    "oracle_curve": task.oracle_how,
                },
                indent=1,
            ),
            encoding="utf-8",
        )
