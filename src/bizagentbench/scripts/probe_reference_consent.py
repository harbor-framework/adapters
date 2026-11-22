"""Offline native public-tool consent probes; scoring is a later separate process.

Uses only recorded public tool requests and the trusted tool service's responses.
Stops at the first attempted execution; does not synthesize successful worlds.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--adapter-root', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve previous probes; use a new output path')
    args.output.mkdir(parents=True)
    service = Path(__file__).with_name('reference_service.py')
    results = []
    for task in json.loads(args.selection.read_text('utf-8'))['tasks']:
        trace = json.loads((args.adapter_root / task['reference'] / 'public-tools.json').read_text('utf-8'))
        for variant in ('approval_pending', 'approval_rejected'):
            target = args.output / variant / task['task_id']
            child = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', str(service),
                                      '--source-dir', str(args.source_dir), '--task-id', task['task_id'],
                                      '--output', str(target)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True, encoding='utf-8')
            skipped_or_changed = False
            try:
                for original in trace:
                    request = {k: original[k] for k in ('actor', 'tool', 'arguments')}
                    if request['actor'] == 'user' and request['tool'] == 'decide_request' and not skipped_or_changed:
                        skipped_or_changed = True
                        if variant == 'approval_pending':
                            continue
                        request['arguments'] = {**request['arguments'], 'decision': 'DECLINE'}
                    child.stdin.write(json.dumps(request) + '\n'); child.stdin.flush()
                    response = json.loads(child.stdout.readline())
                    if request['tool'] == 'execute_request' and skipped_or_changed:
                        if response['ok']:
                            raise AssertionError('Native engine accepted an unapproved write')
                        results.append({'task_id': task['task_id'], 'variant': variant,
                                        'attempted_public_request': request, 'public_response': response,
                                        'unapproved_execution_rejected': True})
                        break
                    if not response['ok']:
                        raise AssertionError(('Prefix failed before target consent check', request, response))
                else:
                    raise AssertionError('No consent boundary exercised')
            finally:
                child.stdin.write('null\n'); child.stdin.flush(); child.stdin.close()
                child.wait(timeout=30)
                if child.returncode:
                    raise RuntimeError('Trusted tool service failed')
    output = {'kind': 'offline_native_public_tool_consent_probe_not_llm_validation',
              'model_calls': 0, 'grader_invoked_by_probe': False, 'probes': results}
    (args.output / 'public-results.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(f'{len(results)} public-tool consent probes rejected unapproved execution; no grader invoked.')


if __name__ == '__main__':
    main()
