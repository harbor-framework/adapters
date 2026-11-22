"""Package a positive control; explicitly separate it from full LLM oracles."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
from bizagentbench.adapter import BizAgentBenchAdapter

parser = argparse.ArgumentParser()
parser.add_argument("--source-dir", type=Path, required=True)
parser.add_argument("--trace", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--task-id", default='case_040')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
fixture = root / "tests/fixtures/reference_provider.py"
spec = importlib.util.spec_from_file_location("reference_provider", fixture)
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)
customer = json.loads((args.source_dir / 'payment/data/private' / f'{args.task_id}.json').read_text('utf-8'))
dialogue_path = args.trace.with_name('customer-dialogue.json')
dialogue = json.loads(dialogue_path.read_text('utf-8')) if dialogue_path.exists() else []
_, messages = provider.messages_from_trace(json.loads(args.trace.read_text("utf-8")), customer['opening'], dialogue)
args.output_dir.mkdir(parents=True, exist_ok=True)
references = args.output_dir / "references"
references.mkdir(exist_ok=True)
(references / f"{args.task_id}.json").write_text(json.dumps(messages, indent=2), "utf-8")
config = json.loads((args.source_dir / "configs/model.example.json").read_text("utf-8"))
config["episode_timeout_seconds"] = max(900, len(json.loads(args.trace.read_text('utf-8'))) * 4 + 120)
for role in ("agent", "user"):
    config[role].update(base_url="http://fixture:9000/v1", model="reference-" + role,
                        max_tokens=4096, timeout_seconds=60, extra_body={}, temperature=0, trust_env=False)
config_path = args.output_dir / "reference-model.json"
config_path.write_text(json.dumps(config, indent=2), "utf-8")
task, = BizAgentBenchAdapter(args.output_dir, args.source_dir, task_ids=[args.task_id],
                            model_config=config_path, oracle_dir=references, overwrite=True).run()
shutil.copy2(fixture, task / "environment/runtime/reference_provider.py")
shutil.copy2(args.trace, task / "environment/runtime/public-tools.json")
(task / 'environment/runtime/customer-context.json').write_text(json.dumps({'opening': customer['opening'], 'dialogue': dialogue}), 'utf-8')
with (task / "environment/docker-compose.yaml").open("a", encoding="utf-8") as handle:
    handle.write('  fixture:\n    image: python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df\n'
                 '    command: ["python", "/reference_provider.py"]\n    volumes:\n'
                 '      - ./runtime/reference_provider.py:/reference_provider.py:ro\n'
                 '      - ./runtime/public-tools.json:/public-tools.json:ro\n'
                 '      - ./runtime/customer-context.json:/customer-context.json:ro\n')
print(f"Prepared {args.task_id} positive control with scripted customer; not live-LLM oracle")
