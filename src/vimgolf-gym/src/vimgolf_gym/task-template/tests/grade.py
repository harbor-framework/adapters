"""VimGolf grader.

Ports vimgolf-gym's ``vimgolf-evaluate.py`` (``--solution-format vimgolf-benchmark
--validator vimgolf-validator --solution-not-longer-than-output``). The replay itself
is the unmodified ``/app/vimgolf-verifier.py single_shot`` shipped in the published
``agile4im/vimgolf-verifier:v0.0.3`` image, run as an unprivileged user (no supplementary
groups, no write access to /app or /logs/verifier) so submitted keystrokes cannot touch
the grader or the reward file.
"""

import hashlib
import json
import os
import pwd
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import vimgolf.vimgolf
from vimgolf.vimgolf import tokenize_keycode_reprs

APP_DIR = Path("/app")
SOLUTION_PATH = APP_DIR / "solution.txt"
GRADING_PATH = Path("/tests/grading.json")
LOG_DIR = Path("/logs/verifier")
ARTIFACTS_DIR = Path("/logs/artifacts")  # Harbor's convention dir, copied from the agent
VERIFIER_SCRIPT = "/app/vimgolf-verifier.py"
REPLAY_USER = "nobody"
# vimgolf-evaluate.py: subprocess.check_output(cmd, timeout=15.0)
REPLAY_TIMEOUT_SEC = 15.0


def lock_down_writable_dirs() -> None:
    """Harbor creates /logs/verifier with mode 0777 and restores artifacts into a
    world-writable /app. Remove write access for the replay user before replaying. The
    owner is kept, so the host can still read and clean up the trial dir; the mode is not
    restored afterwards, which would reopen a window for leftover replay processes."""
    replay_uid = pwd.getpwnam(REPLAY_USER).pw_uid
    for d in (LOG_DIR, APP_DIR):
        if d.stat().st_uid == replay_uid:
            os.chown(d, 0, 0)
        d.chmod(0o755)
    # Hide everything the agent shipped over from the replay. Only the first line of
    # solution.txt is replayed, so the rest of the file (or anything the agent left in
    # Harbor's /logs/artifacts convention dir) could otherwise hold the expected output
    # for a short ":r /app/solution.txt"-style solution to read in. Upstream hands the
    # verifier only the extracted line and deletes it before Vim starts.
    if SOLUTION_PATH.is_file() and not SOLUTION_PATH.is_symlink():
        os.chown(SOLUTION_PATH, 0, 0)
        SOLUTION_PATH.chmod(0o600)
    if ARTIFACTS_DIR.is_dir() and not ARTIFACTS_DIR.is_symlink():
        os.chown(ARTIFACTS_DIR, 0, 0)
        ARTIFACTS_DIR.chmod(0o700)


def _replay_user_pids(replay_uid: int) -> list[int]:
    pids = []
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                if os.stat(f"/proc/{entry}").st_uid == replay_uid:
                    pids.append(int(entry))
            except FileNotFoundError:
                pass
    return pids


def kill_replay_user_processes() -> None:
    """subprocess timeouts only kill the direct child; make sure nothing spawned by the
    replay outlives it. Sweeps until no process of the replay user is left (a process
    forked during a sweep is caught by the next one)."""
    replay_uid = pwd.getpwnam(REPLAY_USER).pw_uid
    for _ in range(100):
        pids = _replay_user_pids(replay_uid)
        if not pids:
            return
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.05)
    raise RuntimeError("replay user processes survived SIGKILL")


def sha256_checksum(content: str) -> str:
    sha256 = hashlib.sha256()
    sha256.update(content.encode("utf-8"))
    return sha256.hexdigest()


def extract_first_non_empty_line(content: str) -> str:
    content = vimgolf.vimgolf.format_(content)
    lines = content.split("\n")
    for line in lines:
        if line.strip():
            return line
    return ""


def run_vimgolf_validator(input_content: str, solution_keys: str) -> tuple[str, str]:
    """Returns (checksum, status) from the upstream single-shot verifier."""
    if not solution_keys:
        return "", "empty_solution"
    workdir = tempfile.mkdtemp(prefix="vimgolf-replay-")
    try:
        input_path = Path(workdir) / "input.txt"
        solution_path = Path(workdir) / "solution.txt"
        input_path.write_text(input_content)
        solution_path.write_text(solution_keys)
        replay_pw = pwd.getpwnam(REPLAY_USER)
        for p in (workdir, input_path, solution_path):
            os.chown(p, replay_pw.pw_uid, replay_pw.pw_gid)
        cmd = [
            "python",
            VERIFIER_SCRIPT,
            "single_shot",
            "--input_content",
            str(input_path),
            "--solution_keys",
            str(solution_path),
            "--load_from_path",
            "--remove_load_paths",
        ]
        try:
            output = subprocess.check_output(
                cmd,
                timeout=REPLAY_TIMEOUT_SEC,
                cwd="/app",
                user=replay_pw.pw_uid,
                group=replay_pw.pw_gid,
                extra_groups=[],
                env={"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                     "HOME": workdir, "LANG": "C.UTF-8"},
                stdin=subprocess.DEVNULL,
            )
            response = json.loads(output)
            return response["checksum"], response.get("status", "")
        except subprocess.CalledProcessError:
            return "", "verifier_error"
        except subprocess.TimeoutExpired:
            return "", "verifier_timeout"
        except json.JSONDecodeError:
            return "", "verifier_bad_json"
        except KeyError:
            return "", "verifier_no_checksum"
    finally:
        kill_replay_user_processes()
        shutil.rmtree(workdir, ignore_errors=True)


def grade() -> dict:
    grading = json.loads(GRADING_PATH.read_text())
    input_raw: str = grading["input"]
    output_sha256: str = grading["output_sha256"]  # sha256(format_(output))
    output_len: int = grading["output_len"]  # len(raw output), the keystroke budget

    details = {"challenge_id": grading["challenge_id"], "keystroke_budget": output_len}
    if SOLUTION_PATH.is_symlink() or not SOLUTION_PATH.is_file():
        details.update(passed=False, reason="solution_missing")
        return details
    try:
        raw_solution = SOLUTION_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        details.update(passed=False, reason="solution_not_utf8")
        return details

    solution = extract_first_non_empty_line(raw_solution)
    details["solution"] = solution
    if not solution:
        details.update(passed=False, reason="solution_empty")
        return details

    key_length = len(tokenize_keycode_reprs(solution))
    details["keystrokes"] = key_length
    if key_length > output_len:
        details.update(passed=False, reason="solution_longer_than_output")
        return details

    checksum, status = run_vimgolf_validator(
        vimgolf.vimgolf.format_(input_raw), solution
    )
    details["replay_status"] = status
    passed = bool(checksum) and checksum == output_sha256
    details.update(passed=passed, reason="ok" if passed else "output_mismatch")
    return details


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        lock_down_writable_dirs()
        details = grade()
        kill_replay_user_processes()
    except Exception as exc:  # grader failure must never award credit
        details = {"passed": False, "reason": f"grader_error: {exc!r}"}
    # drop anything planted earlier; Harbor prefers reward.json over reward.txt
    for name in ("grading_details.json", "reward.txt", "reward.json"):
        (LOG_DIR / name).unlink(missing_ok=True)
    (LOG_DIR / "grading_details.json").write_text(json.dumps(details, indent=2))
    (LOG_DIR / "reward.txt").write_text("1\n" if details.get("passed") else "0\n")


if __name__ == "__main__":
    main()
