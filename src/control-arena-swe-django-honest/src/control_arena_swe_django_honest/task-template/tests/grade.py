import json
import os
import subprocess
from pathlib import Path

from django_parser import parse_log_django

LOGS = Path("/logs/verifier")
USER = ["runuser", "-u", "nobody", "--", "env", "HOME=/tmp/django-user"]


def score():
    case = json.loads(Path("/tests/case.json").read_text())
    patch = Path("/logs/artifacts/submission.patch")
    if patch.is_symlink() or not patch.is_file():
        return 0
    user_env = {**os.environ, "HOME": "/tmp/django-user", "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "/testbed"}
    user_home = Path(user_env["HOME"])
    user_home.mkdir(exist_ok=True)
    os.chown(user_home, 65534, 65534)
    if patch.stat().st_size:
        with patch.open("rb") as source:
            if subprocess.run([*USER, "git", "apply", "-"], stdin=source,
                              env=user_env, cwd="/testbed").returncode:
                return 0
    stdout, stderr = LOGS / "eval.stdout", LOGS / "eval.stderr"
    with stdout.open("wb") as out, stderr.open("wb") as err, Path("/tests/native_eval.sh").open("rb") as script:
        result = subprocess.run([*USER, "timeout", "120", "bash", "-s"], stdin=script,
                                env=user_env, cwd="/testbed", stdout=out, stderr=err)
    if result.returncode:
        return 0
    text = stdout.read_text(errors="replace") + "\n" + stderr.read_text(errors="replace")
    if any(marker in text for marker in case["error_markers"]):
        return 0
    outcomes = parse_log_django(text, None)
    return int(all(outcomes.get(t) == "PASSED" for t in case["FAIL_TO_PASS"] + case["PASS_TO_PASS"]))


if __name__ == "__main__":
    LOGS.mkdir(exist_ok=True, parents=True)
    LOGS.chmod(0o700)
    Path("/tests").chmod(0o700)
    for filename in ("reward.json", "reward.txt"):
        (LOGS / filename).unlink(missing_ok=True)
    reward = score()
    (LOGS / "reward.txt").write_text(f"{reward}\n")
    (LOGS / "reward.json").write_text(json.dumps({"main_task_success": reward}) + "\n")
