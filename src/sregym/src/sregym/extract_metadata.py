"""Extract per-problem metadata from an SREGym checkout.

Run with SREGym's own interpreter from the SREGym repository root, e.g.

    cd /path/to/SREGym && uv run python /path/to/extract_metadata.py --out meta.json

Problem constructors build Kubernetes client objects but do not contact a
cluster, so a placeholder kubeconfig is enough. For every registered problem
this records the app info the conductor's ``/get_app`` endpoint would return,
the stages the conductor would run (from the oracles the problem attaches),
and the agent prompt that SREGym's own Claude Code driver
(``clients.claudecode.driver.build_instruction``) builds from that app info.
The adapter then reproduces that prompt verbatim.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

PLACEHOLDER_KUBECONFIG = """apiVersion: v1
kind: Config
clusters: [{name: placeholder, cluster: {server: "https://127.0.0.1:1"}}]
contexts: [{name: placeholder, context: {cluster: placeholder, user: placeholder}}]
current-context: placeholder
users: [{name: placeholder, user: {token: placeholder}}]
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--api-hostname", default="host.docker.internal")
    parser.add_argument("--api-port", default="8000")
    parser.add_argument("--problems", nargs="*", help="Limit to these problem IDs")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the current KUBECONFIG (a running cluster) for problems whose constructors query it",
    )
    args = parser.parse_args()

    root = Path.cwd()
    sys.path.insert(0, str(root))
    if not args.live:
        kube = Path(tempfile.mkdtemp()) / "kubeconfig"
        kube.write_text(PLACEHOLDER_KUBECONFIG)
        os.environ["KUBECONFIG"] = str(kube)
    # The same values SREGym's agent containers receive.
    os.environ["API_HOSTNAME"] = args.api_hostname
    os.environ["API_PORT"] = args.api_port

    from clients.claudecode.driver import build_instruction  # upstream prompt builder
    from sregym.conductor.problem_sets import PROBLEM_SETS
    from sregym.conductor.problems.registry import ProblemRegistry

    registry = ProblemRegistry()
    ids = args.problems or sorted(registry.get_problem_ids())
    records, failures = [], {}
    for pid in ids:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                problem = registry.get_problem_instance(pid)
            app = problem.app
            namespaces = list(getattr(app, "namespaces", None) or [app.namespace])
            stages = []
            if getattr(problem, "diagnosis_oracle", None) is not None:
                stages.append("diagnosis")
            if getattr(problem, "mitigation_oracle", None) is not None:
                stages.append("mitigation")
            app_info = {
                "app_name": app.app_name,
                "namespace": app.namespace,
                "namespaces": namespaces,
                "descriptions": str(app.description),
                "stages": stages,
            }
            records.append(
                {
                    "problem_id": pid,
                    "problem_class": type(problem).__name__,
                    "app_class": type(app).__name__,
                    "app_info": app_info,
                    "stages": stages,
                    "suites": sorted(name for name, members in PROBLEM_SETS.items() if pid in members),
                    "instruction": build_instruction(app_info),
                }
            )
        except Exception as exc:  # recorded, not fatal: the adapter reports them
            failures[pid] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"

    args.out.write_text(json.dumps({"problems": records, "failures": failures}, indent=2))
    print(f"extracted {len(records)} problems, {len(failures)} failures", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
