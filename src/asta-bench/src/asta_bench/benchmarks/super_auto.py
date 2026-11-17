"""SUPER "Auto" split (AstaBench `super_validation`): verifier-run scoring.

Upstream (`astabench/evals/super/task.py`) scores an Auto sample with
`evaluate_entrypoints`: some executed command must (a) mention the entrypoint
file (or run it as `python -m <module>`), (b) show no `Traceback` and no
`<entrypoint file>: error` in its output, and (c) have run for at least 10
seconds.  Upstream reads that evidence from an agent-writable execution
history, so it can be satisfied without running anything.

Here the agent submits `{command, cwd}` and the verifier runs the command
itself for a short window, applying (a)-(c) to what it observes.  The command
runs as an unprivileged user with no way back to root, so it cannot write the
reward directory or the grader files, or signal the verifier; every process it
leaves behind is killed before the reward is written.

Reference solutions (`super_auto_solutions/<task_id>/`) are real: `solve.sh`
sets up the repository (with any patches it needs to run on CPU) and
`answer.json` holds the command.  Samples without one are not generated and
are listed, with the reason, in `super_auto_excluded.json`.
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

The submitted command is untrusted code, so it runs as SANDBOX_UID with
no_new_privs (setuid/file-capability binaries cannot raise it back to root):
  * /, /logs, /logs/verifier and /tests are made root-owned and not group/other
    writable first, so it cannot write the reward or the grader files, or swap
    the reward directory;
  * it gets ownership of the work trees it may legitimately write (the agent's
    working directories and the caches in $HOME; never system paths, never a
    file with other hard links), so a command that ran for the agent as root
    still runs;
  * a different uid cannot signal or ptrace the verifier;
  * afterwards every process of SANDBOX_UID is SIGKILLed (it cannot change
    uid, so that is every process it started, including detached ones), and
    only then is the reward written, after removing any reward file.
"""

from __future__ import annotations

import ctypes
import json
import os
import pwd
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

ANSWER_FILE = Path("/app/answer.txt")
CONFIG_FILE = Path("/tests/config.json")
REWARD_DIR = Path("/logs/verifier")
REWARD_FILE = REWARD_DIR / "reward.txt"
REWARD_JSON = REWARD_DIR / "reward.json"
LOG_FILE = REWARD_DIR / "entrypoint_run.log"

MIN_SECONDS = 10.0  # upstream: `step_execution_time.total_seconds() < 10` fails
WINDOW_SECONDS = 15.0  # stop here; MIN_SECONDS plus a margin for start-up jitter

SANDBOX_UID = SANDBOX_GID = 54321
SANDBOX_NAME = "super-auto-run"
# Kept root-owned and not writable by the command.
GRADER_DIRS = ("/logs/verifier", "/tests")
LOCKED_ANCESTORS = ("/", "/logs")
# Never given to the command, even when its cwd is inside them.
SYSTEM_PREFIXES = (
    "/logs", "/tests", "/proc", "/sys", "/dev", "/etc", "/bin", "/sbin",
    "/lib", "/lib32", "/lib64", "/libx32", "/usr", "/boot", "/run", "/var",
    "/opt/inspect_tool_support",
)
# Work trees the agent may have set the command up in (contents only for /tmp).
WORK_ROOTS = ("/tmp", "/workspace", "/content", "/app", "/home")

_LIBC = ctypes.CDLL(None, use_errno=True)
_PR_SET_NO_NEW_PRIVS = 38


def _write_reward(value: float) -> None:
    REWARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    REWARD_FILE.write_text(f"{value:.6f}\n")


def _under(path: str, prefixes) -> bool:
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def _lock_down_grader() -> None:
    """Root-own the reward and test trees and every directory above them."""
    for d in LOCKED_ANCESTORS:
        os.chown(d, 0, 0)
        os.chmod(d, stat.S_IMODE(os.lstat(d).st_mode) & ~0o022)
    for top in GRADER_DIRS:
        os.makedirs(top, exist_ok=True)
        for dirpath, dirnames, filenames in os.walk(top):
            for name in [""] + dirnames + filenames:
                path = os.path.join(dirpath, name) if name else dirpath
                st = os.lstat(path)
                os.lchown(path, 0, 0)
                if not stat.S_ISLNK(st.st_mode):
                    os.chmod(path, stat.S_IMODE(st.st_mode) & ~0o022)


def _grant(top: str, include_top: bool, protected: set) -> None:
    """Give SANDBOX_UID the directories and single-link regular files under top.

    Symlinks are not followed, and anything that is a grader tree (by inode,
    so bind mounts are caught too) is skipped."""
    if not os.path.isdir(top) or os.path.islink(top):
        return
    for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
        keep = []
        for d in dirnames:
            path = os.path.join(dirpath, d)
            try:  # entries may vanish while walking
                st = os.lstat(path)
                if stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) not in protected:
                    os.lchown(path, SANDBOX_UID, SANDBOX_GID)
                    keep.append(d)
            except FileNotFoundError:
                pass
        dirnames[:] = keep
        for f in filenames:
            path = os.path.join(dirpath, f)
            try:
                st = os.lstat(path)
                if stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
                    os.lchown(path, SANDBOX_UID, SANDBOX_GID)
            except FileNotFoundError:
                pass
    if include_top:
        os.lchown(top, SANDBOX_UID, SANDBOX_GID)


def _prepare_sandbox_user(cwd: str) -> str:
    """Create the user, lock the grader down, hand over the work trees.

    Returns the HOME the command runs with (root's, so caches the agent filled
    are reused)."""
    if os.geteuid() != 0:
        raise RuntimeError("the SUPER-Auto verifier must run as root")
    try:
        pwd.getpwuid(SANDBOX_UID)
    except KeyError:
        with open("/etc/group", "a") as fh:
            fh.write(f"{SANDBOX_NAME}:x:{SANDBOX_GID}:\n")
        with open("/etc/passwd", "a") as fh:
            fh.write(
                f"{SANDBOX_NAME}:x:{SANDBOX_UID}:{SANDBOX_GID}::/root:/bin/bash\n"
            )

    _lock_down_grader()
    protected = set()
    for d in GRADER_DIRS + LOCKED_ANCESTORS:
        st = os.stat(d)
        protected.add((st.st_dev, st.st_ino))

    home = pwd.getpwuid(0).pw_dir or "/root"
    os.makedirs(os.path.join(home, ".cache"), exist_ok=True)
    os.chmod(home, stat.S_IMODE(os.stat(home).st_mode) | 0o011)
    for name in os.listdir(home):
        path = os.path.join(home, name)
        if os.path.isdir(path) and not os.path.islink(path):
            _grant(path, include_top=True, protected=protected)
    for root in WORK_ROOTS:
        _grant(root, include_top=(root != "/tmp"), protected=protected)
    real_cwd = os.path.realpath(cwd)
    if real_cwd != "/" and not _under(real_cwd, SYSTEM_PREFIXES):
        _grant(real_cwd, include_top=True, protected=protected)
    return home


def _drop_privileges() -> None:
    """preexec_fn: no setuid/file-capability escalation after the uid change."""
    if _LIBC.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_NO_NEW_PRIVS) failed")


def _live_sandbox_pids() -> list[int]:
    pids = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            status = Path(f"/proc/{name}/status").read_text()
        except OSError:
            continue
        fields = dict(
            line.split(":", 1) for line in status.splitlines() if ":" in line
        )
        uids = fields.get("Uid", "").split()
        state = fields.get("State", "").strip()[:1]
        if state != "Z" and str(SANDBOX_UID) in uids:
            pids.append(int(name))
    return pids


def _kill_sandbox_processes(deadline_seconds: float = 30.0) -> None:
    """SIGKILL every process of SANDBOX_UID, wherever it was reparented.

    kill(-1) from a process of that uid reaches all of them at once; it cannot
    reach root's processes."""
    end = time.monotonic() + deadline_seconds
    while _live_sandbox_pids():
        if time.monotonic() > end:
            raise RuntimeError(
                f"processes of uid {SANDBOX_UID} survived SIGKILL: "
                f"{_live_sandbox_pids()}"
            )
        pid = os.fork()
        if pid == 0:  # child: become the sandbox user, kill all of its processes
            try:
                os.setgroups([])
                os.setgid(SANDBOX_GID)
                os.setuid(SANDBOX_UID)
                os.kill(-1, signal.SIGKILL)
            except BaseException:
                pass
            os._exit(0)
        os.waitpid(pid, 0)
        time.sleep(0.2)


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
    """Run `command` in `cwd` as SANDBOX_UID; return (seconds, still running, output)."""
    home = _prepare_sandbox_user(cwd)
    _kill_sandbox_processes()  # nothing of that uid may predate the run
    env = dict(os.environ)
    env.update(HOME=home, USER=SANDBOX_NAME, LOGNAME=SANDBOX_NAME)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("wb") as log:
        start = time.monotonic()
        proc = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            user=SANDBOX_UID,
            group=SANDBOX_GID,
            extra_groups=[],
            preexec_fn=_drop_privileges,
        )
        still_running = False
        try:
            proc.wait(timeout=WINDOW_SECONDS)
        except subprocess.TimeoutExpired:
            still_running = True
        elapsed = time.monotonic() - start
        if still_running:
            # Give the process group a chance to exit cleanly first.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
        # Then everything the command started, detached or not.
        _kill_sandbox_processes()
        proc.wait()
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
    # Its processes are gone and it never had write access here; still, only
    # this verifier's own reward may be collected.
    for stale in (REWARD_JSON, REWARD_FILE):
        stale.unlink(missing_ok=True)
    _write_reward(1.0 if passed else 0.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
