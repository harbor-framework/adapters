"""Trusted construction harness: role-scoped public tools only, no grading RPC.

This process owns the native world. The planner receives only tool responses.
On EOF the trusted harness saves evidence for a subsequent isolated check.
Never deploy this developer harness or its output into the main agent image.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--source-dir', type=Path, required=True)
parser.add_argument('--task-id', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = [str(args.source_dir), str(args.source_dir / 'third_party/tau2-bench/src')]
from payment.runtime.tasks.contracts import read_contract
from payment.runtime.core.factory import make_engine

contract = read_contract(args.task_id, args.source_dir / 'payment/data')
world = deepcopy(contract['initial_world'])
engine = make_engine(world, contract['engine_profile'], args.source_dir / 'payment/data')
args.output.mkdir(parents=True, exist_ok=True)
trace = []
try:
    for line in sys.stdin:
        request = json.loads(line)
        if request is None:
            break
        assert set(request) == {'actor', 'tool', 'arguments'}
        assert request['actor'] in {'assistant', 'user'}
        result = engine.call(request['actor'], request['tool'], **request['arguments'])
        trace.append({**request, 'response': result})
        (args.output / 'public-tools.json').write_text(json.dumps(trace, indent=2), 'utf-8')
        print(json.dumps(result), flush=True)
finally:
    (args.output / 'world.json').write_text(json.dumps(world), 'utf-8')
    (args.output / 'construction.json').write_text(json.dumps({
        'task_id': args.task_id, 'kind': 'scripted_customer_public_tool_reference',
        'tool_calls': len(trace), 'live_llm_verified': False,
        'score_available_to_planner': False,
    }, indent=2), 'utf-8')
