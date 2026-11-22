"""Generate a deterministic transport fixture, never a success/oracle claim."""
import argparse
import json
from pathlib import Path
import shutil
from bizagentbench.adapter import BizAgentBenchAdapter

parser = argparse.ArgumentParser()
parser.add_argument("--source-dir", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--task-ids", nargs="+", default=["case_001", "case_031"])
parser.add_argument("--user-mode", choices=["offline-user", "offline-bad-user", "offline-http-error"], default="offline-user")
parser.add_argument("--agent-mode", choices=["offline-agent", "offline-http-error"], default="offline-agent")
args = parser.parse_args()
args.output_dir.mkdir(parents=True, exist_ok=True)
config = json.loads((args.source_dir / "configs/model.example.json").read_text("utf-8"))
config["episode_timeout_seconds"] = 60
for role, model in (("agent", args.agent_mode), ("user", args.user_mode)):
    config[role].update(base_url="http://fixture:9000/v1", model=model, max_tokens=512, timeout_seconds=20,
                        extra_body={}, temperature=0, trust_env=False)
config_path = args.output_dir / "offline-model.json"
config_path.write_text(json.dumps(config, indent=2), "utf-8")
paths = BizAgentBenchAdapter(args.output_dir, args.source_dir, task_ids=args.task_ids,
                             model_config=config_path, overwrite=True).run()
fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/provider.py"
for path in paths:
    shutil.copy2(fixture, path / "environment/runtime/fixture.py")
    compose = path / "environment/docker-compose.yaml"
    with compose.open("a", encoding="utf-8") as handle:
        handle.write('  fixture:\n    image: python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df\n'
                     '    command: ["python", "/fixture.py"]\n    volumes:\n      - ./runtime/fixture.py:/fixture.py:ro\n')
expected = "Strict=0" if args.user_mode == "offline-user" and args.agent_mode == "offline-agent" else "unscored native error"
print(f"Prepared {len(paths)} offline transport fixtures; expected {expected} (not oracle)")
