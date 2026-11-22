"""Full unmodified native run with local fixtures only; never a paid model run."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
os.environ.setdefault('LOGURU_LEVEL', 'ERROR')

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-dir', type=Path, default=Path('/opt/bizagentbench'))
p.add_argument('--output', type=Path, required=True)
p.add_argument('--task-ids', nargs='+', required=True)
p.add_argument('--variant', default='baseline')
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root / 'tests/fixtures'), str(args.source_dir), str(args.source_dir / 'third_party/tau2-bench/src')]
from adaptive_provider import server
from payment.runtime.interaction.domain import register
from tools.evaluate import run_case
register()
if args.output.exists(): raise FileExistsError('Keep prior attempts')
args.output.mkdir(parents=True)
rows = []
for task in args.task_ids:
    fixture = server(task, args.variant)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    config = json.loads((args.source_dir / 'configs/model.example.json').read_text('utf-8'))
    config['episode_timeout_seconds'] = 900
    for role in ('agent', 'user'):
        config[role].update(base_url=f'http://127.0.0.1:{fixture.server_port}/v1', model='adaptive-' + role,
                            max_tokens=4096, timeout_seconds=60, extra_body={}, temperature=0, trust_env=False)
    try:
        result = run_case(task, config, args.output)
        row = {k: result[k] for k in ('task_id', 'reward', 'termination', 'classification', 'actual_tool_calls')}
        rows.append(row); print(json.dumps(row), flush=True)
    finally:
        fixture.controller.close(); fixture.shutdown(); fixture.server_close()
(args.output / 'summary.json').write_text(json.dumps({'kind': 'adaptive_scripted_native_not_live_llm', 'tasks': rows}, indent=2), encoding='utf-8')
raise SystemExit(0 if all(r['reward'] == 1 for r in rows) else 1)
