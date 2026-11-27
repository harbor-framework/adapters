"""Replay the native marker command on each generated projection of the release.

Run in the generated CDK image with the task tree mounted read-only. No AWS
credentials are needed, and the container can run with networking disabled.
"""

import argparse
import json
import os
import runpy
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    args = parser.parse_args()
    results = []
    for case in sorted(args.tasks.glob("iac-*-honest-*")) + sorted(args.tasks.glob("iac-honest-*")):
        identity = json.loads((case / "tests/source.json").read_text())
        marker = identity["objective"]
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            shutil.copytree(case / "environment/repo", repo)
            tests = repo / "tests"
            tests.mkdir()
            for filename in ("conftest.py", f"test_{marker}.py"):
                shutil.copyfile(case / "tests" / filename, tests / filename)
            for is_oracle in (False, True):
                if is_oracle:
                    subprocess.run(["git", "apply", str(case / "solution/reference.patch")], cwd=repo, check=True)
                xml = Path(tmp) / "pytest.xml"
                run = subprocess.run(
                    ["pytest", "--tb=short", "--no-header", "-q", "-m", marker, "--junitxml", str(xml)],
                    cwd=repo, env=os.environ | {"PYTHONPATH": str(repo), "AWS_EC2_METADATA_DISABLED": "true"},
                    capture_output=True, text=True, check=False,
                )
                if run.returncode not in (0, 1) or not xml.exists():
                    raise RuntimeError(run.stdout + run.stderr)
                passed = run.returncode == 0
                if identity["setting"] == "iac_fast":
                    parse = runpy.run_path(str(case / "tests/fast_junit.py"))["_parse_junit_xml_for_marker"]
                    passed, _ = parse(xml.read_text(), marker)
                results.append([identity["setting"], marker, is_oracle, passed])
                print(*results[-1], flush=True)
    if not results or any(is_oracle != passed for _, _, is_oracle, passed in results):
        raise ValueError("A baseline or oracle returned an unexpected result")


if __name__ == "__main__":
    main()
