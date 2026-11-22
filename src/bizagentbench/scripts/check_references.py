"""Post-construction check, run in a separate network-disabled container.

These are developer diagnostics; formal validation still uses native run_case
and Harbor's separate verifier. Never mount this script in a planner container.
"""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--references', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--upstream', type=Path, default=Path('/opt/bizagentbench'))
args = parser.parse_args()
sys.path[:0] = [str(args.upstream), str(args.upstream / 'third_party/tau2-bench/src')]
from payment.runtime.tasks.contracts import read_contract
from payment.runtime.evaluation.runner import verify
args.output.mkdir(parents=True, exist_ok=True)
rows = []
for path in sorted(args.references.glob('case_*/world.json')):
    task_id = path.parent.name
    verdict = verify(json.loads(path.read_text('utf-8')), read_contract(task_id, args.upstream / 'payment/data'))
    (args.output / f'{task_id}.json').write_text(json.dumps(verdict, indent=2), 'utf-8')
    row = {key: verdict[key] for key in ['goal_success', 'process_success', 'protection_success', 'strict_success']}
    rows.append({'task_id': task_id, **row})
    print(task_id, json.dumps(row), json.dumps(verdict.get('failed_by_category')), flush=True)
(args.output / 'summary.json').write_text(json.dumps({'kind': 'scripted_customer_construction_check_not_live_llm', 'tasks': rows}, indent=2), 'utf-8')
raise SystemExit(0 if rows and all(row['strict_success'] for row in rows) else 1)
