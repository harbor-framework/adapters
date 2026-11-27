"""One pinned cohort/report pipeline for Harbor and upstream metric records."""

import argparse
import subprocess
from pathlib import Path

from .attempts import Records, harbor_records, write_attempts
from .release import load_selection


def original_records(experiment: Path, rows: list[dict]) -> Records:
    from v2w import benchmark, runner

    configs = [
        benchmark.Configuration(r["family"], r["sample"], r["metric_family"])
        for r in rows
    ]
    exp = runner.Experiment(experiment)
    records = exp.records(configs)
    ledger = [
        {
            "family": c.family,
            "sample": c.sample,
            "metrics": str((exp.dir(c) / "metrics.json").resolve()),
            "side": "original",
            "status": "recorded",
        }
        for c in configs
        if exp.dir(c).is_dir()
    ]
    return Records(records, ledger)


def write_report(rows: list[dict], records: Records, out: Path) -> dict:
    from v2w import scoring

    if any(
        (out / name).exists()
        for name in ("summary.json", "samples.json", "samples.csv", "attempts.json")
    ):
        raise FileExistsError(f"{out}: use a fresh report directory")
    if records.issues:
        write_attempts(rows, records, out)
        raise ValueError(
            f"invalid Harbor attempts; see {out}/attempts.json: {'; '.join(records.issues)}"
        )
    config = scoring.load_config()
    report = scoring.score(records.metrics, scoring.make_scope(rows, config), config)
    statuses = {
        (row["family"], row["sample"]): row["status"] for row in report["samples"]
    }
    for attempt in records.attempts:
        pair = (attempt["family"], attempt["sample"])
        attempt["upstream_status"] = statuses[pair]
        if attempt["status"] in ("recorded", "scored"):
            attempt["status"] = (
                "scored"
                if statuses[pair] in ("ok", "build_failed")
                else "incomplete"
                if records.metrics.get(pair) is None
                else "invalid_result"
            )
    write_attempts(rows, records, out)
    scoring.write_report(report, out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("upstream-root", "data-root", "selection", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--results", type=Path, help="one Harbor job directory")
    source.add_argument(
        "--experiment", type=Path, help="one upstream experiment directory"
    )
    args = parser.parse_args()
    try:
        rows = load_selection(args.upstream_root, args.data_root, args.selection)
        records = (
            harbor_records(args.results, rows)
            if args.results is not None
            else original_records(args.experiment, rows)
        )
        report = write_report(rows, records, args.out)
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"video2world-score: {exc}\n")
    if report["readiness"] != "ready":
        parser.exit(
            1,
            f"V2WScore blocked: {len(report['issues'])} issues; see {args.out}/summary.json\n",
        )
    print(
        f"V2WScore {report['v2w_score']:.6f} ({report['configurations']} configurations, {report['families']} families)"
    )


if __name__ == "__main__":
    main()
