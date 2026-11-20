"""SUPER "Auto" split (AstaBench `super_validation`): replay-based scoring.

Upstream (`astabench/evals/super/task.py`) scores an Auto sample with
`evaluate_entrypoints`: some executed command must (a) mention the entrypoint
file (or run it as `python -m <module>`), (b) show no `Traceback` and no
`<entrypoint file>: error` in its output, and (c) have run for at least 10
seconds.  Upstream reads that evidence from an agent-writable execution
history, so it can be satisfied without running anything.

Here the agent submits `{command, cwd}`.  After the agent has finished, Harbor
runs REPLAY_PY in the agent's container (a `[[verifier.collect]]` hook): it
runs the command for a short window, as an unprivileged user, and records how
long it ran and what it printed.  The verifier runs in a separate container,
receives that record as an artifact and applies (a)-(c) to it.  The submitted
command therefore never shares a container with the reward or the grader.

Reference solutions (`super_auto_solutions/<task_id>/`) are real: `solve.sh`
sets up the repository (with any patches it needs to run on CPU) and
`answer.json` holds the command.  Samples without one are not generated and
are listed, with the reason, in `super_auto_excluded.json`.
"""

from __future__ import annotations

import base64
import gzip
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


REPLAY_PY = r'''"""SUPER-Auto replay: run the submitted command and record what happened.

Harbor runs this in the agent's container after the agent has finished (a
`[[verifier.collect]]` hook in task.toml; the script is carried in the hook's
command, not stored in the container).  It runs the submitted command for a
short window and writes what it observed -- how long the command ran and what
it printed -- to EVIDENCE_DIR, which Harbor then hands to the verifier.  The
verifier runs in a separate container and applies upstream's rule to that
record; nothing here computes a reward.

The submitted command is untrusted code, so it runs as SANDBOX_UID with
no_new_privs (setuid/file-capability binaries cannot raise it back to root):
  * EVIDENCE_DIR and the directories above it are root-owned and not
    group/other writable, so it cannot write or swap the record;
  * it gets ownership of the trees it may legitimately write (every
    non-system top-level directory, the entries of /tmp and /opt, the
    directories in root's home; never system paths, never a file with other
    hard links) and a HOME of its own that links to root's, so a command that
    ran for the agent as root still runs.  It cannot create new top-level
    directories or files directly in root's home;
  * directories on root's PATH / LD_LIBRARY_PATH (e.g. /root/.local/bin), their
    contents and their ancestors are never handed over, so it cannot plant a
    program that root runs later (Harbor's `tar` of the artifacts);
  * a different uid cannot signal or ptrace this process;
  * afterwards every process of SANDBOX_UID is SIGKILLed (it cannot change
    uid, so that is every process it started, including detached ones), and
    only then is the record written.
"""

from __future__ import annotations

import ctypes
import json
import os
import pwd
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ANSWER_FILE = Path("/app/answer.txt")
EVIDENCE_DIR = Path("/var/lib/super-auto")
EVIDENCE_FILE = EVIDENCE_DIR / "evidence.json"
OUTPUT_FILE = EVIDENCE_DIR / "output.log"

WINDOW_SECONDS = 15.0  # upstream requires 10 s; the margin covers start-up jitter

SANDBOX_UID = SANDBOX_GID = 54321
SANDBOX_NAME = "super-auto-run"
# Kept root-owned and not writable by the command.
GRADER_DIRS = (str(EVIDENCE_DIR),)
LOCKED_ANCESTORS = ("/", "/var", "/var/lib")
# Never given to the command, even when its cwd is inside them.  Every other
# top-level directory is (the agent worked as root and may have used any of
# them: /workspace, /app, /mnt, /content, ...).  /root is handled via HOME,
# /tmp and /opt per entry.
SYSTEM_PREFIXES = (
    "/logs", "/tests", "/proc", "/sys", "/dev", "/etc", "/bin", "/sbin",
    "/lib", "/lib32", "/lib64", "/libx32", "/usr", "/boot", "/run", "/var",
    "/root", "/tmp", "/opt", "/lost+found",
)
PER_ENTRY_ROOTS = ("/tmp", "/opt")  # grant each entry, not the directory itself
NEVER_GRANTED = ("/opt/inspect_tool_support",)

_LIBC = ctypes.CDLL(None, use_errno=True)
_PR_SET_NO_NEW_PRIVS = 38


def _under(path: str, prefixes) -> bool:
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def _lock_down_grader() -> None:
    """Root-own the evidence directory and every directory above it."""
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


def _grant(top: str, include_top: bool, protected: set, exec_dirs: tuple = ()) -> None:
    """Give SANDBOX_UID the directories and single-link regular files under top.

    Symlinks are not followed, and anything that is a grader tree (by inode,
    so bind mounts are caught too) is skipped.  Best effort: a read-only tree
    is skipped whole, an entry that cannot be changed is skipped (the command
    may then fail to write there; it never gains anything).

    exec_dirs are directories root resolves programs or libraries from after
    the run (PATH, LD_LIBRARY_PATH): they, their contents and their ancestors
    stay root's, so nothing can be planted there for root to run."""

    def is_exec(path: str) -> bool:
        return any(path == d or path.startswith(d + "/") for d in exec_dirs)

    def is_exec_ancestor(path: str) -> bool:
        return any(d.startswith(path.rstrip("/") + "/") for d in exec_dirs)

    if is_exec(top):
        return
    try:
        st = os.lstat(top)
        if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) in protected:
            return
        os.lchown(top, st.st_uid, st.st_gid)  # probe: fails on a read-only fs
    except OSError:
        return

    def chown(path: str) -> None:
        try:
            os.lchown(path, SANDBOX_UID, SANDBOX_GID)
        except OSError:
            pass

    for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
        keep = []
        for d in dirnames:
            path = os.path.join(dirpath, d)
            try:  # entries may vanish while walking
                st = os.lstat(path)
            except OSError:
                continue
            if (
                stat.S_ISDIR(st.st_mode)
                and (st.st_dev, st.st_ino) not in protected
                and not is_exec(path)
            ):
                if not is_exec_ancestor(path):
                    chown(path)
                keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            path = os.path.join(dirpath, f)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
                chown(path)
    if include_top and not is_exec_ancestor(top):
        chown(top)


def _prepare_sandbox_user(cwd: str) -> str:
    """Create the user, lock the grader down, hand over the work trees.

    Returns the HOME the command runs with: a fresh directory it owns, holding
    a symlink to every entry of root's home, so caches the agent filled are
    reused and new dot-directories (~/.allennlp, ...) can still be created,
    while root's own home and shell start-up files stay root's."""
    if os.geteuid() != 0:
        raise RuntimeError("the SUPER-Auto replay must run as root")
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

    exec_dirs = tuple(sorted({
        os.path.realpath(d)
        for var in ("PATH", "LD_LIBRARY_PATH")
        for d in os.environ.get(var, "").split(":")
        if d.startswith("/")
    }))

    def grant(path: str, include_top: bool) -> None:
        if not _under(path, NEVER_GRANTED):
            _grant(path, include_top=include_top, protected=protected,
                   exec_dirs=exec_dirs)

    # Every non-system top-level directory, and each entry of /tmp and /opt.
    for name in os.listdir("/"):
        path = "/" + name
        if not _under(path, SYSTEM_PREFIXES):
            grant(path, include_top=True)
    for root in PER_ENTRY_ROOTS:
        if os.path.isdir(root):
            for name in os.listdir(root):
                grant(os.path.join(root, name), include_top=True)
    real_cwd = os.path.realpath(cwd)
    if real_cwd != "/" and not _under(
        real_cwd, tuple(p for p in SYSTEM_PREFIXES if p not in ("/root", "/tmp", "/opt"))
    ):
        grant(real_cwd, include_top=True)

    # Root's home: its directories become the command's, its files stay root's.
    root_home = pwd.getpwuid(0).pw_dir or "/root"
    os.chmod(root_home, stat.S_IMODE(os.stat(root_home).st_mode) | 0o011)
    entries = sorted(os.listdir(root_home))
    for name in entries:
        path = os.path.join(root_home, name)
        if os.path.isdir(path) and not os.path.islink(path):
            grant(path, include_top=True)
    home = tempfile.mkdtemp(prefix="super-auto-home-", dir="/tmp")
    for name in entries:
        os.symlink(os.path.join(root_home, name), os.path.join(home, name))
    os.chown(home, SANDBOX_UID, SANDBOX_GID)
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


def run_for_window(command: str, cwd: str) -> tuple[float, bool]:
    """Run `command` in `cwd` as SANDBOX_UID; return (seconds, still running)."""
    home = _prepare_sandbox_user(cwd)
    _kill_sandbox_processes()  # nothing of that uid may predate the run
    env = dict(os.environ)
    env.update(HOME=home, USER=SANDBOX_NAME, LOGNAME=SANDBOX_NAME)
    with OUTPUT_FILE.open("wb") as log:
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
    return elapsed, still_running


def _write_evidence(record: dict) -> None:
    tmp = EVIDENCE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(record), encoding="utf-8")
    os.replace(tmp, EVIDENCE_FILE)


def main() -> int:
    # Start from an empty, root-only evidence directory: nothing the agent
    # left there may reach the verifier.
    if EVIDENCE_DIR.is_symlink() or EVIDENCE_DIR.is_file():
        EVIDENCE_DIR.unlink()
    elif EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, mode=0o755)

    raw = _read_answer()
    if raw is None:
        _write_evidence({"status": "invalid", "reason": "answer.txt missing or unreadable"})
        return 0
    answer = extract_json_from_response(raw)
    command = answer.get("command") if isinstance(answer, dict) else None
    cwd = answer.get("cwd") if isinstance(answer, dict) else None
    if not isinstance(command, str) or not command.strip():
        _write_evidence({"status": "invalid", "reason": "answer has no `command` string"})
        return 0
    if not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd):
        _write_evidence({
            "status": "invalid",
            "reason": f"answer `cwd` is not an existing absolute directory: {cwd!r}",
        })
        return 0

    elapsed, still_running = run_for_window(command, cwd)
    print(f"ran {elapsed:.1f}s (still running at window end: {still_running})",
          file=sys.stderr)
    _write_evidence({
        "status": "ran",
        "command": command,
        "cwd": cwd,
        "elapsed_seconds": elapsed,
        "still_running_at_window_end": still_running,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

EVIDENCE_DIR = "/var/lib/super-auto"
# The replay window is 15 s; the rest is for handing the work trees to the
# replay user (a walk over everything the agent installed) and for clean-up.
COLLECT_TIMEOUT_SEC = 600


def collect_command() -> str:
    """Shell command of the `[[verifier.collect]]` hook that runs REPLAY_PY.

    The script travels inside the command (task.toml is not in the agent's
    container), so the agent cannot edit it beforehand.  A record left by the
    agent is removed first, even if the script then fails to start."""
    blob = base64.b64encode(gzip.compress(REPLAY_PY.encode("utf-8"), mtime=0)).decode("ascii")
    return (
        f"rm -rf {EVIDENCE_DIR}; "
        f"echo {blob} | base64 -d | gunzip | python3 -"
    )


RUN_SCORER_PY = r'''"""SUPER-Auto verifier: apply upstream's rule to the replay record.

Upstream's `evaluate_entrypoints` (astabench/evals/super/task.py) passes a
sample when some executed command
  * mentions the entrypoint file name, or uses `python -m` with its module
    name,
  * shows no `Traceback` and no `<entrypoint file>: error` in its output, and
  * ran for at least 10 seconds.
Upstream reads that from an execution history the agent can write.  Here the
record comes from a replay that Harbor runs in the agent's container after the
agent has finished (see the `[[verifier.collect]]` hook in task.toml): the
submitted command, how long it ran and what it printed.  This verifier runs in
a separate container and only reads that record.

No record means the replay itself did not run (an infrastructure failure):
the verifier fails and no reward is recorded.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_FILE = Path("/tests/config.json")
EVIDENCE_FILE = Path("/var/lib/super-auto/evidence.json")
OUTPUT_FILE = Path("/var/lib/super-auto/output.log")
REWARD_DIR = Path("/logs/verifier")
REWARD_FILE = REWARD_DIR / "reward.txt"
LOG_FILE = REWARD_DIR / "entrypoint_run.log"

MIN_SECONDS = 10.0  # upstream: `step_execution_time.total_seconds() < 10` fails


def _write_reward(value: float) -> None:
    REWARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    REWARD_FILE.write_text(f"{value:.6f}\n")


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


def main() -> int:
    cfg = json.loads(CONFIG_FILE.read_text())
    entrypoint = cfg["entrypoint"]
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        raise RuntimeError("config has no entrypoint")

    if not EVIDENCE_FILE.is_file():
        raise RuntimeError(
            f"{EVIDENCE_FILE} is missing: the replay did not run in the agent's "
            "environment, so there is nothing to score"
        )
    record = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    status = record.get("status")
    if status == "invalid":
        print(f"invalid answer: {record.get('reason')}", file=sys.stderr)
        _write_reward(0.0)
        return 0
    if status != "ran":
        raise RuntimeError(f"unexpected replay record: {record!r}")

    command = record["command"]
    elapsed = float(record["elapsed_seconds"])
    output = OUTPUT_FILE.read_bytes().decode("utf-8", errors="replace")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(output, encoding="utf-8")

    if not mentions_entrypoint(entrypoint, command):
        print(f"command does not run the entrypoint {entrypoint!r}", file=sys.stderr)
        _write_reward(0.0)
        return 0
    clean = output_is_clean(entrypoint, output)
    passed = elapsed >= MIN_SECONDS and clean
    print(
        f"entrypoint={entrypoint!r} ran {elapsed:.1f}s (still running at window "
        f"end: {record.get('still_running_at_window_end')}) clean_output={clean} "
        f"-> {'PASS' if passed else 'FAIL'}",
        file=sys.stderr,
    )
    _write_reward(1.0 if passed else 0.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
