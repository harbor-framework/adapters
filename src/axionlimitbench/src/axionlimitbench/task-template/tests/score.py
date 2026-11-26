"""Grade one result file against the reference curve for one paper.

The grading itself is the unmodified scorer package in /tests/scorer. This
wrapper only (1) coerces the submitted JSON the same way the original driver
does, (2) calls the scorer for this one paper, and (3) applies the headline
rule of the original leaderboard: a submission succeeds when it is compared
and its median residual is at most log10(1.1) dex (within 10 percent).

Usage: score.py <result.json> <log dir>
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TAU = math.log10(1.1)

SNAPSHOT_FIELDS = (
    "paper_title",
    "coupling_type",
    "is_new_limit",
    "is_projection",
    "data_points",
    "data_source",
    "dm_density_assumed",
    "confidence_level",
    "extraction_confidence",
    "suggested_experiment_name",
    "coupling_convention",
    "notes",
)


def normalise_result(raw: dict) -> tuple[dict, list[str]]:
    """Coerce a result file into the snapshot schema; never raises.

    Same rules as ``normalise_result`` in the original reference driver.
    """
    problems: list[str] = []
    out: dict = {}
    for k in SNAPSHOT_FIELDS:
        out[k] = raw.get(k)
    pts = []
    for p in raw.get("data_points") or []:
        try:
            if isinstance(p, dict):
                m, g = float(p.get("mass_eV", p.get("mass"))), float(p.get("coupling"))
            else:
                m, g = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError, KeyError):
            problems.append(f"bad point {p!r}")
            continue
        if not (m > 0 and g > 0) or m != m or g != g:
            problems.append(f"non-positive/nan point {p!r}")
            continue
        pts.append([m, g])
    out["data_points"] = pts
    out["num_points"] = len(pts)
    out["is_new_limit"] = (
        bool(raw.get("is_new_limit")) if raw.get("is_new_limit") is not None else bool(pts)
    )
    out["is_projection"] = bool(raw.get("is_projection", False))
    if out["data_source"] is None:
        out["data_source"] = "none" if not pts else "unknown"
    for k in ("confidence_level", "extraction_confidence", "dm_density_assumed"):
        v = out.get(k)
        if v is not None:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                problems.append(f"non-numeric {k}={v!r}")
                out[k] = None
    if out["confidence_level"] is None:
        out["confidence_level"] = 0.95
    if out["extraction_confidence"] is None:
        out["extraction_confidence"] = 0.5
    for k in ("paper_title", "suggested_experiment_name", "notes", "coupling_convention"):
        if out.get(k) is not None and not isinstance(out[k], str):
            out[k] = json.dumps(out[k])
    return out, problems


def grade(arxiv_id: str, prediction: dict) -> dict:
    os.environ["AAL_EXCLUDE_PROJECTIONS"] = "1"
    sys.path.insert(0, str(TESTS_DIR))
    import scorer.evaluate as ev
    from scorer.ground_truth import load_ground_truth

    entries = [e for e in load_ground_truth() if e.arxiv_id == arxiv_id and not e.is_projection]
    if not entries:
        raise RuntimeError(f"no reference entry for {arxiv_id}")
    metrics = ev.compute_all_metrics(entries, [prediction] * len(entries))
    rows = [p for p in metrics.get("per_paper") or [] if p.get("arxiv_id") == arxiv_id]
    if len(rows) != 1:
        raise RuntimeError(f"expected one scored row for {arxiv_id}, got {len(rows)}")
    row = rows[0]
    status = row.get("comparison_status")
    if status is None and row.get("status") == "excluded_gt":
        status = "excluded_gt"
    interp = row.get("interp_metrics") or {}
    try:
        residual = float(interp.get("median_residual_dex"))
    except (TypeError, ValueError):
        residual = float("nan")
    finite = math.isfinite(residual)
    return {
        "comparison_status": status,
        "median_residual_dex": residual if finite else None,
        "success": bool(status == "compared" and finite and residual <= TAU),
        "within_factor_two": bool(status == "compared" and finite and residual <= 0.3),
        "coupling_type_predicted": row.get("coupling_type_predicted"),
        "coupling_type_expected": row.get("coupling_type_expected"),
        "coupling_type_correct": row.get("coupling_type_correct"),
        "scored_via": row.get("scored_via"),
        "num_points_extracted": row.get("num_points_extracted"),
    }


def main() -> int:
    result_path, log_dir = Path(sys.argv[1]), Path(sys.argv[2])
    log_dir.mkdir(parents=True, exist_ok=True)
    arxiv_id = json.loads((TESTS_DIR / "task.json").read_text())["arxiv_id"]
    report: dict = {"arxiv_id": arxiv_id, "success": False, "tolerance_dex": TAU}

    raw = None
    if not result_path.is_file():
        report["error"] = "result file not found"
    else:
        try:
            raw = json.loads(result_path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, RecursionError) as exc:
            report["error"] = f"result file is not valid JSON: {exc}"
        else:
            if not isinstance(raw, dict):
                report["error"] = "result file is not a JSON object"
                raw = None

    if raw is not None:
        prediction, problems = normalise_result(raw)
        prediction["arxiv_id"] = arxiv_id
        report["problems"] = problems[:20]
        report.update(grade(arxiv_id, prediction))

    reward = 1 if report["success"] else 0
    (log_dir / "score.json").write_text(json.dumps(report, indent=2, default=str))
    (log_dir / "reward.txt").write_text(f"{reward}\n")
    print(json.dumps(report, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
