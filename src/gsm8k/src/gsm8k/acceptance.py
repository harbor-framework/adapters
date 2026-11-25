"""Plan and reconcile deterministic GSM8K controls on Docker or Podman."""

from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json

from harbor.models.job.lock import TrialLock
from harbor.models.trial.result import TrialResult
from harbor.publisher.packager import Packager

from .adapter import ANSWER_PATH, HARBOR_VERSION, read_source


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def answer_for(gold, case):
    if case == "empty":
        return ""
    if case == "malformed":
        return "not a number\n"
    if case == "comma":
        return f"{Decimal(gold):,}\n"
    if case == "wrong":
        return f"{Decimal(gold) + 1:f}\n"
    if case != "oracle":
        raise ValueError(f"Unknown control: {case}")
    return f"{gold}\n"


def control(row, task, case):
    return {
        "task_name": row.task_name, "source_row": row.row,
        "source_line_sha256": row.line_sha256, "task_digest": task["task_digest"],
        "harbor_checksum": task["harbor_checksum"], "instruction_sha256": task["files"]["instruction.md"],
        "case": case, "submission": answer_for(row.gold, case), "upstream_answer": row.upstream_answer,
        "expected_reward": int(case in ("oracle", "comma")),
    }


def planned_controls(dataset, source, split, extract_answer):
    manifest_raw = (dataset / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    rows = read_source(source.read_bytes(), split)
    tasks = {task["task_name"]: task for task in manifest["tasks"]}
    if manifest["source"]["split"] != split or list(tasks) != [row.task_name for row in rows]:
        raise ValueError(f"Expected the complete {split} dataset")
    for row in rows:
        task = tasks[row.task_name]
        if (task["source_line_sha256"] != row.line_sha256 or task["source_row"] != row.row
                or extract_answer(row.upstream_answer) != row.gold):
            raise ValueError(f"Source alignment failed for {row.task_name}")
    format_row = next(row for row in rows if abs(Decimal(row.gold)) >= 1000)
    formats = [control(format_row, tasks[format_row.task_name], case) for case in ("empty", "malformed", "comma")]
    numbers = [control(row, tasks[row.task_name], case) for row in rows for case in ("oracle", "wrong")]
    return sha256(manifest_raw).hexdigest(), formats + numbers


def grouped_controls(records):
    cases = defaultdict(list)
    for record in records:
        cases[record["case"]].append(record)
    return cases


def verify_payload(dataset, records):
    tasks = {record["task_name"]: record["task_digest"] for record in records}
    for name, digest in tasks.items():
        digest_raw, _ = Packager.compute_content_hash(dataset / name)
        if digest != f"sha256:{digest_raw}":
            raise ValueError(f"Staged task content digest mismatch for {name}")


def trial_submission(trial_dir):
    entries = load(trial_dir / "artifacts/manifest.json")
    matches = [entry for entry in entries if entry["source"] == ANSWER_PATH]
    if len(matches) != 1 or matches[0]["type"] != "file" or matches[0]["status"] != "ok":
        raise ValueError(f"Answer collection incomplete for {trial_dir.name}")
    collected = trial_dir / matches[0]["destination"]
    artifact_root = (trial_dir / "artifacts").resolve()
    if collected.is_symlink() or not collected.is_file() or not collected.resolve().is_relative_to(artifact_root):
        raise ValueError(f"Unexpected collected submission path for {trial_dir.name}")
    return collected.read_bytes()


def check_trial(trial, lock, record, provider):
    phases = (trial.environment_setup, trial.agent_setup, trial.agent_execution, trial.verifier)
    agent = "oracle" if record["case"] == "oracle" else "gsm8k-answer-replay"
    if (trial.exception_info or not trial.finished_at or any(
            not phase or not phase.started_at or not phase.finished_at or phase.finished_at < phase.started_at
            for phase in phases)):
        raise ValueError(f"Trial did not finish cleanly: {trial.trial_name}")
    if (trial.task_name != f"gsm8k/{record['task_name']}" or lock.task.name != record["task_name"]
            or lock.task.digest != record["task_digest"]
            or trial.task_checksum != record["harbor_checksum"] or trial.verifier_environment_mode != "separate"
            or trial.agent_info.name != agent or trial.agent_info.model_info is not None
            or trial.config.environment.type != provider):
        raise ValueError(f"Unexpected native trial configuration: {trial.trial_name}")


def reconcile(result_path, trial, record, provider, is_correct):
    trial_dir = result_path.parent
    lock = TrialLock.model_validate_json((trial_dir / "lock.json").read_bytes())
    check_trial(trial, lock, record, provider)
    submission = trial_submission(trial_dir)
    actual_digest = sha256(submission).hexdigest()
    verifier = trial_dir / "verifier"
    evidence = load(verifier / "answer-evidence.json")
    if evidence != {"status": "read", "bytes_read": len(submission), "sha256": actual_digest}:
        raise ValueError(f"Verifier received different bytes: {trial.trial_name}")
    if submission != record["submission"].encode():
        raise ValueError(f"Submission differs from planned control: {trial.trial_name}")
    expected = int(is_correct("#### " + submission.decode(), {"answer": record["upstream_answer"]}))
    reward_bytes = (verifier / "reward.txt").read_bytes()
    if (expected != record["expected_reward"] or not trial.verifier_result
            or trial.verifier_result.rewards != {"reward": expected} or reward_bytes.strip() != str(expected).encode()):
        raise ValueError(f"Harbor and upstream rewards differ: {trial.trial_name}")
    return {key: record[key] for key in ("case", "task_name", "task_digest", "source_row", "source_line_sha256")} | {
        "trial_id": str(trial.id), "provider": provider, "reward": expected,
        "upstream_reward": expected, "submission_bytes": len(submission), "submission_sha256": actual_digest,
        "trial_sha256": sha256(result_path.read_bytes()).hexdigest(),
        "reward_sha256": sha256(reward_bytes).hexdigest(), "harbor_version": HARBOR_VERSION,
    }


def collect_case(job, records, provider, is_correct):
    pending = {record["task_name"]: record for record in records}
    receipts, failures = [], []
    for path in sorted(job.glob("*/result.json")):
        trial = TrialResult.model_validate_json(path.read_bytes())
        record = pending.pop(trial.task_name.removeprefix("gsm8k/"), None)
        if record is None:
            raise ValueError(f"Unexpected or duplicate trial: {path}")
        if trial.exception_info:
            failures.append({"task_name": record["task_name"], "case": record["case"],
                             "exception_type": trial.exception_info.exception_type, "trial_id": str(trial.id)})
        else:
            receipts.append(reconcile(path, trial, record, provider, is_correct))
    failures.extend({"task_name": record["task_name"], "case": record["case"], "exception_type": "NoTrialResult"}
                    for record in pending.values())
    return receipts, failures
