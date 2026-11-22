"""Run a scripted reference through unmodified native run_case."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
import os
os.environ.setdefault('LOGURU_LEVEL', 'ERROR')

parser = argparse.ArgumentParser()
parser.add_argument("--trace", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--upstream", type=Path, default=Path("/opt/bizagentbench"))
parser.add_argument('--task-id', default='case_040')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reference_provider", root / "tests/fixtures/reference_provider.py")
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)
customer = json.loads((args.upstream / 'payment/data/private' / f'{args.task_id}.json').read_text('utf-8'))
dialogue_path = args.trace.with_name('customer-dialogue.json')
dialogue = json.loads(dialogue_path.read_text('utf-8')) if dialogue_path.exists() else []
server = provider.server(json.loads(args.trace.read_text("utf-8")), opening=customer['opening'], dialogue=dialogue)
threading.Thread(target=server.serve_forever, daemon=True).start()
sys.path[:0] = [str(args.upstream), str(args.upstream / "third_party/tau2-bench/src")]
from payment.runtime.interaction.domain import register
from tools.evaluate import run_case
register()
config = json.loads((args.upstream / "configs/model.example.json").read_text("utf-8"))
config["episode_timeout_seconds"] = max(900, len(json.loads(args.trace.read_text('utf-8'))) * 4 + 120)
for role in ("agent", "user"):
    config[role].update(base_url=f"http://127.0.0.1:{server.server_port}/v1", model="reference-" + role,
                        max_tokens=4096, timeout_seconds=60, extra_body={}, temperature=0, trust_env=False)
args.output.mkdir(parents=True, exist_ok=True)
try:
    result = run_case(args.task_id, config, args.output)
    print(json.dumps({"reward": result["reward"], "termination": result["termination"],
                      "classification": result["classification"], "tool_calls": result["actual_tool_calls"]}))
    assert result["reward"] == 1 and result["verification"]["strict_success"]
finally:
    server.shutdown()
