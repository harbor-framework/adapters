"""Prepare a separate, explicitly offline adaptive-reference Harbor dataset."""
import argparse
import json
from pathlib import Path
import shutil
from bizagentbench.adapter import BizAgentBenchAdapter

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-dir', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--variant', default='baseline')
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
if args.output.exists(): raise FileExistsError('Keep previous adaptive datasets')
args.output.mkdir(parents=True)
config = json.loads((args.source_dir / 'configs/model.example.json').read_text('utf-8'))
config['episode_timeout_seconds'] = 900
for role in ('agent', 'user'):
    config[role].update(base_url='http://fixture:9000/v1', model='adaptive-' + role,
                        max_tokens=4096, timeout_seconds=60, extra_body={}, temperature=0, trust_env=False)
path = args.output / 'offline-model.json'
path.write_text(json.dumps(config, indent=2), encoding='utf-8')
tasks = BizAgentBenchAdapter(args.output, args.source_dir,
                            task_ids=['case_040', 'case_031', 'case_001', 'case_049', 'case_036'],
                            model_config=path).run()
for task in tasks:
    task_id = json.loads((task / 'source.json').read_text('utf-8'))['task_id']
    runtime = task / 'environment/runtime'
    for target in (runtime / 'adaptive-src/bizagentbench', task / 'solution/bizagentbench'):
        target.mkdir(parents=True)
        (target / '__init__.py').write_text('', encoding='utf-8')
        for name in ('adaptive.py', 'adaptive_plans.py'):
            shutil.copy2(root / 'src/bizagentbench' / name, target / name)
    for name in ('adaptive_customer.py', 'adaptive_provider.py'):
        shutil.copy2(root / 'tests/fixtures' / name, runtime / name)
    shutil.copy2(root / 'src/bizagentbench/adaptive_run.py', task / 'solution/adaptive_run.py')
    (task / 'solution/solve.sh').write_text('#!/bin/sh\nset -eu\nexport PYTHONPATH=/solution\nexec python /solution/adaptive_run.py --task-id ' + task_id + '\n', encoding='utf-8', newline='\n')
    with (task / 'environment/docker-compose.yaml').open('a', encoding='utf-8') as handle:
        handle.write('  fixture:\n    image: python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df\n'
                     '    command: ["python", "/fixture/adaptive_provider.py"]\n    environment:\n'
                     '      BIZ_ADAPTIVE_SOURCE: /adaptive-src\n      BIZ_TASK_ID: ' + task_id + '\n      BIZ_VARIANT: ' + args.variant + '\n'
                     '    volumes:\n      - ./runtime/adaptive_provider.py:/fixture/adaptive_provider.py:ro\n'
                     '      - ./runtime/adaptive_customer.py:/fixture/adaptive_customer.py:ro\n'
                     '      - ./runtime/adaptive-src:/adaptive-src:ro\n')
print('Prepared 5 offline adaptive tasks; no real-provider configuration or user fixture in the assistant solution.')
