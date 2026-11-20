"""Read every Harbor trial using Harbor's own result and failure policies."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import MANIFEST_SHA256, UPSTREAM_REVISION
from .release import key, task_id


@dataclass
class Records:
    metrics: dict[tuple[str, str], dict | None]
    attempts: list[dict]
    issues: list[str] = field(default_factory=list)


def harbor_records(results: Path, rows: list[dict]) -> Records:
    try:
        from harbor.models.trial.config import TrialConfig
        from harbor.models.trial.result import TrialResult
    except ImportError as exc:
        raise RuntimeError(
            "Harbor result ingestion requires Python 3.12+ and the 'harbor' extra; use uv run --python 3.12 --extra harbor video2world-score"
        ) from exc

    names = {}
    for row in rows:
        pair = (row["family"], row["sample"])
        slug = task_id(key(row))
        names[slug] = names["aetherlabsai/video2world-" + slug] = pair
    collected = Records({}, [])
    seen = set()
    for directory in sorted(p for p in results.iterdir() if p.is_dir()):
        entry = {
            "side": "harbor",
            "trial": directory.name,
            "result": str((directory / "result.json").resolve()),
            "configuration": str((directory / "config.json").resolve()),
            "status": "incomplete",
            "exceptions": [],
            "reward": None,
            "reward_valid": False,
            "metrics": str((directory / "verifier/metrics.json").resolve())
            if (directory / "verifier/metrics.json").is_file()
            else None,
        }
        collected.attempts.append(entry)
        pair = None
        try:
            result_path = directory / "result.json"
            result = (
                TrialResult.model_validate_json(result_path.read_text())
                if result_path.exists()
                else None
            )
            if result is not None:
                name = result.task_name
                entry.update(
                    {
                        "started_at": result.started_at.isoformat()
                        if result.started_at
                        else None,
                        "finished_at": result.finished_at.isoformat()
                        if result.finished_at
                        else None,
                        "agent": result.agent_info.model_dump(mode="json"),
                        "verifier_mode": result.verifier_environment_mode.value
                        if result.verifier_environment_mode
                        else None,
                    }
                )
                exceptions = [result.exception_info] + [
                    step.exception_info for step in result.step_results or []
                ]
                entry["exceptions"] = [
                    {
                        "type": exc.exception_type,
                        "message": exc.exception_message,
                        "cause": exc.policy.cause.value,
                    }
                    for exc in exceptions
                    if exc is not None
                ]
                rewards = (
                    result.verifier_result.rewards if result.verifier_result else None
                )
                entry["reward"] = rewards.get("reward") if rewards else None
                entry["reward_valid"] = result.reward_valid
            else:
                config = TrialConfig.model_validate_json(
                    (directory / "config.json").read_text()
                )
                name = config.task.name or (
                    config.task.path.name if config.task.path else None
                )
            if name not in names:
                raise ValueError(f"unexpected or unidentified task {name!r}")
            pair = names[name]
            entry.update({"family": pair[0], "sample": pair[1]})
            if pair in seen:
                raise ValueError(
                    f"duplicate attempt for {pair}; use one cohort, one run at a time"
                )
            seen.add(pair)
            collected.metrics[pair] = None
            if result is None or result.finished_at is None:
                continue
            if not result.reward_valid:
                entry["status"] = "exception" if entry["exceptions"] else "no_reward"
                continue
            verifier = directory / "verifier"
            identity = json.loads((verifier / "identity.json").read_text())
            if (
                (identity["family"], identity["sample"]) != pair
                or identity["upstream_revision"] != UPSTREAM_REVISION
                or identity["manifest_sha256"] != MANIFEST_SHA256
            ):
                raise ValueError("mismatched result provenance")
            report = json.loads((verifier / "report/summary.json").read_text())
            if (
                report["readiness"] != "ready"
                or entry["reward"] != report["v2w_score"] / 100
            ):
                raise ValueError("Harbor reward does not match a ready upstream report")
            metrics = verifier / "metrics.json"
            record = json.loads(metrics.read_text())
            if not isinstance(record, dict):
                raise TypeError("metrics.json must contain an object")
            collected.metrics[pair] = record
            entry.update({"status": "scored", "metrics": str(metrics.resolve())})
        except OSError as exc:
            entry.update(
                {"status": "missing_artifacts", "error": f"{type(exc).__name__}: {exc}"}
            )
            if pair is None:
                collected.issues.append(f"{directory.name}: {exc}")
        except (ValueError, KeyError, TypeError) as exc:
            entry.update(
                {"status": "invalid_result", "error": f"{type(exc).__name__}: {exc}"}
            )
            collected.issues.append(f"{directory.name}: {exc}")
            if pair is not None:
                collected.metrics[pair] = None
    return collected


def write_attempts(rows: list[dict], records: Records, out: Path) -> None:
    expected = {(r["family"], r["sample"]) for r in rows}
    observed = {(a["family"], a["sample"]) for a in records.attempts if "family" in a}
    present = {pair for pair, record in records.metrics.items() if record is not None}
    counts = {
        "attempted": len(records.attempts),
        "scored": sum(a["status"] == "scored" for a in records.attempts),
        "incomplete": sum(a["status"] == "incomplete" for a in records.attempts),
    }
    counts["failed"] = counts["attempted"] - counts["scored"] - counts["incomplete"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "attempts.json").write_text(
        json.dumps(
            {
                "counts": counts,
                "attempts": records.attempts,
                "missing": sorted(expected - present),
                "not_attempted": sorted(expected - observed),
                "issues": records.issues,
            },
            indent=2,
        )
        + "\n"
    )
