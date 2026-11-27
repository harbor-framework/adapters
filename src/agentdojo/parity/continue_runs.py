"""Continue a running sanity pair through three rounds, with fail-closed checks.

This controller never retries or overwrites attempts, changes models, or publishes
results. Its integrity checks do not replace scientific review of the results.
"""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from aggregate import aggregate
from aggregate import stage as check_stage


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def process_identity(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart=,comm="],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def stage_check(workspace, stage):
    result = check_stage(workspace, stage)
    write_json(workspace / f"checked-{stage}.json", result)
    return result


def source_hashes():
    folder = Path(__file__).resolve().parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.glob("*.py"))}


def main(args):
    workspace = args.workspace.resolve()
    status_file = workspace / "continuation-status.json"
    # Keep the lock held for the entire process, preventing duplicate controllers.
    with (workspace / "continuation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = {"pid": os.getpid(), "status": "waiting_for_sanity",
                 "stage": "sanity", "source_hashes": source_hashes()}

        def update(**values):
            state.update(values, updated_at_epoch=time.time())
            write_json(status_file, state)
            print(json.dumps({k: state[k] for k in ("status", "stage")}), flush=True)

        try:
            update()
            identities = {pid: process_identity(pid) for pid in args.sanity_pids}
            deadline = time.monotonic() + 12 * 3600
            while any(identity and process_identity(pid) == identity
                      for pid, identity in identities.items()):
                if time.monotonic() > deadline:
                    raise TimeoutError("Sanity did not finish within twelve hours")
                time.sleep(30)
            stage_check(workspace, "sanity")
            update(status="sanity_checked")
            for stage in ("1", "2", "3"):
                if source_hashes() != state["source_hashes"]:
                    raise ValueError("Runner source changed; review before continuing")
                if any((workspace / "runs" / stage / side).exists() for side in ("original", "harbor")):
                    raise ValueError(f"Round {stage} exists; refusing to repeat or overwrite")
                update(stage=stage, status="running")
                processes = []
                handles = []
                try:
                    for side in ("original", "harbor"):
                        command = ["uv", "run", "--script", str(Path(__file__).with_name("run.py")),
                                   "--workspace", str(workspace), "run", "--side", side,
                                   "--round", stage, "--env-file", str(args.env_file),
                                   "--harbor", str(args.harbor)]
                        output = (workspace / f"round-{stage}-{side}.log").open("x")
                        handles.append(output)
                        processes.append(subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT))
                    # Both sides finish the current stage; a failure blocks later rounds.
                    while any(p.poll() is None for p in processes):
                        time.sleep(30)
                    if any(p.returncode != 0 for p in processes):
                        raise RuntimeError(f"Round {stage} runner failed; see preserved logs")
                finally:
                    for handle in handles:
                        handle.close()
                stage_check(workspace, stage)
                update(status="stage_checked")
            result = aggregate(workspace, ["1", "2", "3"])
            write_json(workspace / "parity-results.json", result)
            update(status="running_generalization", stage="generalization")
            command = ["uv", "run", "--script", str(Path(__file__).with_name("run.py")),
                       "--workspace", str(workspace), "run", "--side", "codex",
                       "--round", "generalization", "--env-file", str(args.env_file),
                       "--harbor", str(args.harbor)]
            with (workspace / "generalization.log").open("x") as output:
                subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)
            update(status="completed_awaiting_review")
        except Exception as exc:
            update(status="stopped_needs_review", error=str(exc))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workspace", "env-file", "harbor"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--sanity-pids", nargs="+", type=int, required=True)
    try:
        main(parser.parse_args())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Continuation stopped: {exc}", file=sys.stderr)
        sys.exit(1)
