"""SUPER "Auto" split (AstaBench `super_validation`): verifier-run scoring.

Upstream (`astabench/evals/super/task.py`) scores an Auto sample with
`evaluate_entrypoints`: some executed command must (a) mention the entrypoint
file (or run it as `python -m <module>`), (b) show no `Traceback` and no
`<entrypoint file>: error` in its output, and (c) have run for at least 10
seconds.  Upstream takes the command, its output and its timestamps from an
execution history that the agent can write (its own answer JSON, or
`jupyter_cell_history.json` in its working directory), so the metric can be
satisfied without running anything.

Here the rule is the same but the evidence is produced by the verifier: the
agent submits the command it used and the directory it ran it in; the verifier
runs that command itself for a short window and applies (a)-(c) to what it
observes.  The agent's claims about output or timing are never used.

Reference solutions (`super_auto_solutions/<task_id>/`) are real: `solve.sh`
clones the repository, installs pinned dependencies into a virtualenv, fetches
data and applies whatever small patches the repository needs to run on CPU,
and `answer.json` holds the command.  A task without a working reference
solution is not generated; `super_auto_excluded.json` lists each one with the
reason.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SOLUTIONS_DIR = _HERE / "super_auto_solutions"
EXCLUDED_FILE = _HERE / "super_auto_excluded.json"

# Upstream `super_validation` is `super(split="Auto", sample_limit=50)`.
AUTO_SAMPLE_LIMIT = 50

INSPECT_TASK = "astabench/super_validation"

# Appended to upstream's `Sample.input` (the SUPER `query`) on both parity
# sides.  Upstream finds the command in the execution history; a verifier that
# re-runs it needs it stated.
SUBMIT_INSTRUCTIONS = """

---

## How to submit

When the entrypoint script runs, submit the exact shell command you used to
run it and the directory you ran it from, as a JSON object:

```
{"command": "<shell command that runs the entrypoint script>", "cwd": "<absolute path of the directory to run it in>"}
```

The command is executed again, from that directory, to check your work: it must
run the entrypoint script for at least 10 seconds without raising an error.
Make it self-contained (absolute paths or paths relative to `cwd`; any
environment variables written inline).
"""

HARBOR_FILE_NOTE = "\nWrite that JSON object, and nothing else, to `/app/answer.txt`.\n"


def load_excluded() -> dict[str, str]:
    """task_id -> reason, for Auto samples with no working reference solution."""
    if not EXCLUDED_FILE.exists():
        return {}
    return json.loads(EXCLUDED_FILE.read_text(encoding="utf-8"))


def load_solution(task_id: str) -> tuple[str, dict[str, str]] | None:
    """Return (solve.sh text, {"command", "cwd"}) or None if not provided."""
    sol_dir = SOLUTIONS_DIR / task_id
    solve = sol_dir / "solve.sh"
    answer = sol_dir / "answer.json"
    if not solve.is_file() or not answer.is_file():
        return None
    payload = json.loads(answer.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("command"), str)
        or not isinstance(payload.get("cwd"), str)
        or not payload["command"].strip()
        or not payload["cwd"].startswith("/")
    ):
        raise ValueError(f"super-auto: malformed answer.json for {task_id}")
    return solve.read_text(encoding="utf-8"), {
        "command": payload["command"],
        "cwd": payload["cwd"],
    }


def render_solve_sh(solve_sh: str, answer: dict[str, str]) -> str:
    """Oracle: prepare the environment for real, then submit the command."""
    body = solve_sh.rstrip("\n")
    return (
        body
        + "\n\n# --- submit the command for the verifier to re-run ---\n"
        + "mkdir -p /app\n"
        + "cat > /app/answer.txt <<'SUPER_AUTO_ANSWER_EOF'\n"
        + json.dumps(answer)
        + "\nSUPER_AUTO_ANSWER_EOF\n"
    )


RUN_SCORER_PY = r'''"""SUPER-Auto verifier: re-run the submitted entrypoint command.

Applies upstream's `evaluate_entrypoints` rule (astabench/evals/super/task.py)
to an execution the verifier performs itself, instead of to an agent-supplied
history:

  * the command mentions the entrypoint file name, or uses `python -m` with
    its module name                                   (upstream, verbatim);
  * the command is still running, or has finished, after MIN_SECONDS with no
    `Traceback` and no `<entrypoint file>: error` in its output so far.

The command is stopped at WINDOW_SECONDS; whatever would happen later is not
part of the rule ("ran for more than 10 seconds ... without error").
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ANSWER_FILE = Path("/app/answer.txt")
CONFIG_FILE = Path("/tests/config.json")
REWARD_FILE = Path("/logs/verifier/reward.txt")
LOG_FILE = Path("/logs/verifier/entrypoint_run.log")

MIN_SECONDS = 10.0  # upstream: `step_execution_time.total_seconds() < 10` fails
WINDOW_SECONDS = 15.0  # stop here; MIN_SECONDS plus a margin for start-up jitter


def _write_reward(value: float) -> None:
    REWARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    REWARD_FILE.write_text(f"{value:.6f}\n")


def _read_answer():
    # A missing file, a directory, or undecodable bytes is an invalid answer
    # (reward 0), never a verifier crash.
    try:
        if not ANSWER_FILE.is_file():
            return None
        return ANSWER_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"answer.txt unreadable: {e}", file=sys.stderr)
        return None


def extract_json_from_response(response: str):
    """Verbatim from astabench/evals/utils.py: first `{` to last `}`."""
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start == -1 or json_end == -1:
        return None
    try:
        return json.loads(response[json_start:json_end])
    except json.JSONDecodeError:
        try:
            return json.loads(response[json_start + 1 : json_end - 1])
        except json.JSONDecodeError:
            return None


def mentions_entrypoint(entrypoint: str, command: str) -> bool:
    """Verbatim logic of upstream evaluate_entrypoints' command match."""
    entrypoint_filename = os.path.basename(entrypoint)
    ran_entrypoint = entrypoint_filename in command
    if not ran_entrypoint:
        ran_entrypoint = (
            entrypoint_filename.replace(".py", "").replace("/", ".") in command
            and "python -m" in command
        )
    return ran_entrypoint


def output_is_clean(entrypoint: str, observation: str) -> bool:
    """Verbatim logic of upstream evaluate_entrypoints' output checks."""
    entrypoint_filename = os.path.basename(entrypoint)
    if "Traceback" in observation:
        return False
    if f"{entrypoint_filename}: error" in observation:
        return False
    return True


def run_for_window(command: str, cwd: str) -> tuple[float, bool, str]:
    """Run `command` in `cwd`; return (seconds it ran, still running, output)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("wb") as log:
        start = time.monotonic()
        proc = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        still_running = False
        try:
            proc.wait(timeout=WINDOW_SECONDS)
        except subprocess.TimeoutExpired:
            still_running = True
        elapsed = time.monotonic() - start
        if still_running:
            # Stop the whole process group (entrypoints often spawn children).
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    continue
    output = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    return elapsed, still_running, output


def main() -> int:
    cfg = json.loads(CONFIG_FILE.read_text())
    entrypoint = cfg["entrypoint"]
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        raise RuntimeError("config has no entrypoint")

    raw = _read_answer()
    if raw is None:
        print("answer.txt missing or unreadable", file=sys.stderr)
        _write_reward(0.0)
        return 0

    answer = extract_json_from_response(raw)
    command = answer.get("command") if isinstance(answer, dict) else None
    cwd = answer.get("cwd") if isinstance(answer, dict) else None
    if not isinstance(command, str) or not command.strip():
        print("answer has no `command` string", file=sys.stderr)
        _write_reward(0.0)
        return 0
    if not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd):
        print(f"answer `cwd` is not an existing absolute directory: {cwd!r}",
              file=sys.stderr)
        _write_reward(0.0)
        return 0
    if not mentions_entrypoint(entrypoint, command):
        print(f"command does not run the entrypoint {entrypoint!r}", file=sys.stderr)
        _write_reward(0.0)
        return 0

    elapsed, still_running, output = run_for_window(command, cwd)
    clean = output_is_clean(entrypoint, output)
    passed = elapsed >= MIN_SECONDS and clean
    print(
        f"entrypoint={entrypoint!r} ran {elapsed:.1f}s "
        f"(still running at window end: {still_running}) clean_output={clean} "
        f"-> {'PASS' if passed else 'FAIL'}",
        file=sys.stderr,
    )
    _write_reward(1.0 if passed else 0.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
