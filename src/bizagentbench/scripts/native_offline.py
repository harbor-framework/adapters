"""Run the same clock/close trajectory in unmodified native run_case."""
import argparse
from copy import deepcopy
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading

parser = argparse.ArgumentParser()
parser.add_argument("--upstream", type=Path, default=Path("/opt/bizagentbench"))
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--task-ids", nargs="+", default=["case_001", "case_031"])
parser.add_argument("--user-mode", default="offline-user")
parser.add_argument("--agent-mode", default="offline-agent")
args = parser.parse_args()
sys.path[:0] = [str(args.upstream), str(args.upstream / "third_party/tau2-bench/src")]
fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/provider.py"
spec = importlib.util.spec_from_file_location("fixture_provider", fixture)
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)
server = ThreadingHTTPServer(("127.0.0.1", 0), provider.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
from payment.runtime.interaction.domain import register
from tools.evaluate import run_case
register()
config = json.loads((args.upstream / "configs/model.example.json").read_text("utf-8"))
config["episode_timeout_seconds"] = 60
for role in ("agent", "user"):
    config[role].update(base_url=f"http://127.0.0.1:{server.server_port}/v1",
                        model=args.user_mode if role == "user" else args.agent_mode, max_tokens=512, timeout_seconds=20,
                        extra_body={}, temperature=0, trust_env=False)
args.output.mkdir(parents=True, exist_ok=True)
try:
    for task_id in args.task_ids:
        result = run_case(task_id, deepcopy(config), args.output)
        if args.user_mode == "offline-user" and args.agent_mode == "offline-agent":
            assert result["reward"] == 0, result
            assert result["termination"] == "user_stop", result
            assert result["actual_tool_calls"] == 1, result
        else:
            assert result["reward"] is None, result
            expected = "simulator_protocol_error" if args.user_mode == "offline-bad-user" else "infrastructure_invalid"
            assert result["classification"] == expected, result
finally:
    server.shutdown()
print("Native offline transport trajectories complete (not model parity or oracle)")
