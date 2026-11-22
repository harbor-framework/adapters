"""Partition and execute the full, model-free GSM8K acceptance run."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from .acceptance import collect_case, grouped_controls, load, planned_controls, save, verify_payload
from .adapter import HARBOR_VERSION, require_harbor
from .reference import load_reference


def write_plan(output, ident, provider, split, manifest_sha256, records):
    if not records:
        return
    path = output / provider / f"{ident}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    save(path, {"id": ident, "provider": provider, "split": split, "manifest_sha256": manifest_sha256,
                "records": records})


def write_chunks(output, choices, provider, split, digest):
    for offset in range(0, len(choices), 64):
        write_plan(output, f"{split}-{offset // 64:04d}", provider, split, digest, choices[offset:offset + 64])


def belongs_to_local(record):
    return record["source_row"] < 256 or record["case"] not in ("oracle", "wrong")


def split_plan(output, records, split, digest):
    if split == "train":
        write_chunks(output, records, "docker", split, digest)
        return
    local = [record for record in records if belongs_to_local(record)]
    remote = [record for record in records if not belongs_to_local(record)]
    local_smoke = [record for record in local if record["task_name"] == "gsm8k-test-0017"
                   and record["case"] in ("oracle", "wrong")]
    remote_smoke = [record for record in remote if record["task_name"] == "gsm8k-test-0256"]
    write_plan(output, "test-smoke", "podman", split, digest, local_smoke)
    write_plan(output, "test-smoke", "docker", split, digest, remote_smoke)
    write_chunks(output, [r for r in local if r not in local_smoke], "podman", split, digest)
    write_chunks(output, [r for r in remote if r not in remote_smoke], "docker", split, digest)


def build_plan(datasets, sources, output, scorer):
    extract_answer, _ = load_reference(scorer)
    output.mkdir(parents=True, exist_ok=False)
    for split in ("test", "train"):
        digest, records = planned_controls(datasets / f"gsm8k-{split}", sources / f"gsm8k-{split}.jsonl",
                                           split, extract_answer)
        split_plan(output, records, split, digest)
        print(f"Planned {len(records)} controls for {split}", flush=True)


def job_config(output, name, dataset, case, records, provider, concurrency):
    agent = {"name": "oracle"}
    if case != "oracle":
        answers = {record["instruction_sha256"]: record["submission"] for record in records}
        answers_path = output / f"{name}-answers.json"
        save(answers_path, answers)
        agent = {"import_path": "gsm8k.controls:AnswerReplayAgent", "kwargs": {"answers_path": str(answers_path)}}
    return {
        "job_name": name, "jobs_dir": str(output / "jobs"), "environment": {"type": provider}, "agents": [agent],
        "tasks": [{"path": str(dataset / record["task_name"])} for record in records],
        "n_concurrent_trials": concurrency, "n_attempts": 1, "retry": {"max_retries": 0},
    }


def execute_case(output, name, config):
    job = output / "jobs" / name
    if job.exists():
        raise FileExistsError(f"Keep existing trial evidence and schedule missing controls separately: {job}")
    path = output / f"{name}-config.json"
    save(path, config)
    harbor = Path(sys.executable).parent / "harbor"
    with (output / f"{name}.log").open("xb") as log:
        return subprocess.run([str(harbor), "run", "--config", str(path)], stdout=log, stderr=subprocess.STDOUT,
                              check=False, timeout=1800).returncode


def audit_shard(plan, output, scorer):
    _, is_correct = load_reference(scorer)
    records, failures = [], []
    for case, selected in grouped_controls(plan["records"]).items():
        receipts, missing = collect_case(output / "jobs" / case, selected, plan["provider"], is_correct)
        records.extend(receipts)
        failures.extend(missing)
    return {"id": plan["id"], "provider": plan["provider"], "split": plan["split"],
            "manifest_sha256": plan["manifest_sha256"], "receipts": records, "unscored": failures}


def run_shard(dataset, plan, output, scorer, concurrency):
    require_harbor()
    verify_payload(dataset, plan["records"])
    output.mkdir(parents=True, exist_ok=False)
    save(output / "runtime.json", {"harbor_version": HARBOR_VERSION, "architecture": platform.machine(),
                                   "manifest_sha256": plan["manifest_sha256"], "provider": plan["provider"]})
    for case, selected in grouped_controls(plan["records"]).items():
        config = job_config(output, case, dataset, case, selected, plan["provider"], concurrency)
        code = execute_case(output, case, config)
        print(f"{plan['id']} {case} Harbor exit={code}", flush=True)
    evidence = audit_shard(plan, output, scorer)
    save(output / "evidence.json", evidence)
    print(f"{plan['id']} valid={len(evidence['receipts'])} unscored={len(evidence['unscored'])}", flush=True)
    return evidence


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    for field in ("datasets", "sources", "output", "scorer"):
        plan.add_argument(f"--{field}", type=Path, required=True)
    for name in ("run", "audit"):
        command = commands.add_parser(name)
        for field in ("plan", "output", "scorer"):
            command.add_argument(f"--{field}", type=Path, required=True)
        if name == "run":
            command.add_argument("--dataset", type=Path, required=True)
            command.add_argument("--concurrency", type=int, choices=(1, 2, 3, 4), required=True)
    return parser


def main():
    args = argument_parser().parse_args()
    if args.command == "plan":
        build_plan(args.datasets, args.sources, args.output, args.scorer)
        return
    plan = load(args.plan)
    if args.command == "run":
        evidence = run_shard(args.dataset.resolve(), plan, args.output.resolve(), args.scorer, args.concurrency)
    else:
        evidence = audit_shard(plan, args.output, args.scorer)
        print(json.dumps(evidence, sort_keys=True))
    if evidence["unscored"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
