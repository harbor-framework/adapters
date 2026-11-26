#!/bin/bash
# MLOps-Bench verifier.
#
# Runs the task's public fail-to-pass (F2P) and pass-to-pass (P2P) behavioral
# tests against the agent-edited /workspace and writes:
#   reward          1.0 iff every scoring test passes (task completion), else 0.0
#   test_pass_rate  passed scoring tests / published scoring test count
#   f2p_passed, p2p_passed  per-suite passed counts
#
# The denominators are the upstream published counts (one per `test_*`
# function), so an import error or a collection failure counts every test in
# that suite as failed instead of shrinking the denominator.
#
# This runs in a separate verifier container built from tests/Dockerfile
# (task.toml: environment_mode = "separate"), with the tests and pinned pytest
# baked in and the agent's /workspace restored as an artifact. pytest is
# started with `python -I` (ignores PYTHONPATH, user site-packages and the
# current directory), so files in /workspace cannot shadow pytest or inject a
# sitecustomize. /workspace is added to sys.path only through pytest's
# `pythonpath` option, after pytest itself has loaded. Conftest discovery is
# confined to /tests.

mkdir -p /logs/verifier
# Never trust a pre-existing reward: always recompute from the test suites.
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json

F2P_TOTAL={{F2P_COUNT}}
P2P_TOTAL={{P2P_COUNT}}

cd /tests

# Record the exact grading toolchain for reproducibility.
{ python -I -V; python -I -m pip freeze --all; } > /logs/verifier/toolchain.txt 2>&1

run_suite() {
  local suite="$1"
  timeout 240 python -I -m pytest -p no:cacheprovider -q -rA \
    --rootdir=/tests --confcutdir=/tests -o pythonpath=/workspace \
    --junitxml="/logs/verifier/junit_${suite}.xml" \
    "/tests/test_${suite}.py" 2>&1 | tee "/logs/verifier/pytest_${suite}.log"
}

run_suite f2p
run_suite p2p

python -I - "$F2P_TOTAL" "$P2P_TOTAL" <<'PY'
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

f2p_total, p2p_total = int(sys.argv[1]), int(sys.argv[2])
log_dir = Path("/logs/verifier")


def passed_count(suite: str) -> int:
    path = log_dir / f"junit_{suite}.xml"
    if not path.exists():
        return 0
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return 0
    passed = 0
    for case in root.iter("testcase"):
        if not case.get("name", "").startswith("test_"):
            continue
        if any(child.tag in {"failure", "error", "skipped"} for child in case):
            continue
        passed += 1
    return passed


f2p_passed = min(passed_count("f2p"), f2p_total)
p2p_passed = min(passed_count("p2p"), p2p_total)
total = f2p_total + p2p_total
passed = f2p_passed + p2p_passed
resolved = total > 0 and passed == total

rewards = {
    "reward": 1.0 if resolved else 0.0,
    "test_pass_rate": round(passed / total, 6) if total else 0.0,
    "f2p_passed": f2p_passed,
    "p2p_passed": p2p_passed,
}
(log_dir / "reward.json").write_text(json.dumps(rewards))
(log_dir / "reward.txt").write_text(f"{rewards['reward']}\n")
print(
    f"F2P {f2p_passed}/{f2p_total}  P2P {p2p_passed}/{p2p_total}  "
    f"resolved={resolved}  test_pass_rate={rewards['test_pass_rate']}"
)
PY

# Fallback so the verifier always produces a reward even if the scorer crashed.
if [ ! -s /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi
exit 0
