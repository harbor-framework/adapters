"""Offline batch utilities; scripted-customer evidence is never model parity."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['native', 'prepare'])
parser.add_argument('--references', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--source-dir', type=Path, default=Path('/opt/bizagentbench'))
args = parser.parse_args()
scripts = Path(__file__).resolve().parent
attempts = []
for path in sorted(args.references.glob('case_*/public-tools.json')):
    task_id = path.parent.name
    trace = json.loads(path.read_text('utf-8'))
    if not trace or trace[-1]['tool'] != 'record_case_outcome' or not trace[-1]['response']['ok']:
        raise ValueError(f'Incomplete construction: {task_id}')
    if args.mode == 'native':
        command = [sys.executable, str(scripts / 'native_reference.py'), '--task-id', task_id,
                   '--upstream', str(args.source_dir), '--trace', str(path), '--output', str(args.output)]
    else:
        command = [sys.executable, '-X', 'utf8', str(scripts / 'prepare_reference.py'), '--task-id', task_id,
                   '--source-dir', str(args.source_dir), '--trace', str(path), '--output-dir', str(args.output)]
    try:
        result = subprocess.run(command, timeout=max(960,len(trace)*4+180), check=False)
        attempt = {'task_id': task_id, 'exit_code': result.returncode}
    except subprocess.TimeoutExpired:
        attempt = {'task_id': task_id, 'exit_code': 124, 'error': 'offline_runner_timeout'}
    attempts.append(attempt)
    print(task_id, args.mode, attempt['exit_code'], flush=True)
args.output.mkdir(parents=True, exist_ok=True)
(args.output / f'{args.mode}-batch.json').write_text(json.dumps({
    'kind': 'scripted_customer_not_live_llm', 'attempts': attempts,
}, indent=2), 'utf-8')
raise SystemExit(any(row['exit_code'] for row in attempts))
