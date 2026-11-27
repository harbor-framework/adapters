"""Run trusted checks around a separate, unprivileged Python 3.4 filesystem."""

import errno
import json
import os
import resource
import signal
import stat
import subprocess
import tempfile
from pathlib import Path

from comparison import check_solutions_equal

RUNNER = ["/usr/sbin/chroot", "--userspec=65534:65534", "--groups=65534", "/opt/apps-runtime",
          "/usr/local/bin/python"]
LOGS = Path("/logs/verifier")


def limit_output() -> None:
    limit = 10 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))


def run_case(code: str, stdin: str, expected: str) -> bool:
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(
                [*RUNNER, "-c", code], stdin=subprocess.PIPE, stdout=out, stderr=err,
                start_new_session=True, preexec_fn=limit_output,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
            )
        except OSError as exc:
            if exc.errno == errno.E2BIG:
                return False
            raise
        try:
            proc.communicate(input=stdin.encode(), timeout=10)
        except subprocess.TimeoutExpired:
            return False
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        out.seek(0)
        err.seek(0)
        return (
            proc.returncode == 0
            and err.read().strip() != b"Timeout"
            and check_solutions_equal(out.read().decode(errors="replace").strip(), expected.strip())
        )


def read_code(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("code"), str):
        return payload["code"]
    return None


def grade() -> None:
    LOGS.mkdir(exist_ok=True, parents=True)
    for filename in ["reward.json", "reward.txt"]:
        (LOGS / filename).unlink(missing_ok=True)
    # Docker populates /dev at runtime; the copied legacy root has an empty /dev.
    for name, mode in [("urandom", 0o444), ("random", 0o444), ("null", 0o666), ("zero", 0o444)]:
        path = Path("/opt/apps-runtime/dev") / name
        if not path.exists():
            os.mknod(path, stat.S_IFCHR | mode, (Path("/dev") / name).stat().st_rdev)
            path.chmod(mode)
    # A broken image, isolation setup, or test packet is an infrastructure error.
    subprocess.run([*RUNNER, "-c", "import sys; assert sys.version_info[:2] == (3, 4)"],
                   check=True, timeout=10)
    packet = json.loads(Path("/tests/cases.json").read_text(encoding="utf-8"))
    cases = packet["cases"]
    if not 1 <= len(cases) <= 10:
        raise ValueError("Expected one to ten native tests")
    code = read_code(Path("/logs/artifacts/submission.json"))
    reward = int(code is not None and "\0" not in code and
                 all(run_case(code, stdin, expected) for stdin, expected in cases))
    (LOGS / "reward.txt").write_text(f"{reward}\n", encoding="utf-8")
    (LOGS / "reward.json").write_text(json.dumps({"main_task_success": reward}) + "\n",
                                      encoding="utf-8")


if __name__ == "__main__":
    grade()
