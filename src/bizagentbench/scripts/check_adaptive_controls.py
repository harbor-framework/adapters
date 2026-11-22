"""Exercise adaptive assistant + variable scripted customer through public tools.

Native state is owned by reference_service; scoring happens later in separate
containers. No real model, private contract or grader import in this program.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def run(task, variant, source, output, root):
    from bizagentbench.adaptive import AdaptiveController
    spec = importlib.util.spec_from_file_location('adaptive_customer', root / 'tests/fixtures/adaptive_customer.py')
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    policy = fixture.CustomerPolicy(variant)
    service = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', str(root / 'scripts/reference_service.py'),
                                '--source-dir', str(source), '--task-id', task, '--output', str(output)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8')
    def call(actor, tool, arguments):
        service.stdin.write(json.dumps({'actor': actor, 'tool': tool, 'arguments': arguments}) + '\n'); service.stdin.flush()
        line = service.stdout.readline()
        if not line: raise RuntimeError('Native public service exited')
        return json.loads(line)
    controller = AdaptiveController(task)
    messages, shift, original_id, actual_id = [], False, None, None
    try:
        for _ in range(1000):
            response = controller.next({'messages': messages})
            messages.append({'role': 'assistant', **response})
            if response.get('tool_calls'):
                for request in response['tool_calls']:
                    function = request['function']; arguments = json.loads(function['arguments'])
                    if variant == 'id_shift' and not shift and function['name'] == 'call_discoverable_agent_tool':
                        shadow = call('assistant', function['name'], arguments)
                        if shadow.get('ok') and isinstance(shadow.get('data'), dict) and shadow['data'].get('status') == 'PENDING':
                            original_id = shadow['data']['id']
                            listed = call('user', 'get_my_requests', {})
                            assert listed['ok']
                            decline = call('user', 'decide_request', {'request_id': original_id, 'decision': 'DECLINE'})
                            assert decline['ok']; shift = True
                        else:
                            # Do not duplicate a non-proposal business mutation.
                            result = shadow
                            messages.append({'role': 'tool', 'tool_call_id': request['id'], 'content': json.dumps(result)})
                            continue
                    result = call('assistant', function['name'], arguments)
                    if shift and actual_id is None and function['name'] == 'call_discoverable_agent_tool':
                        actual_id = result['data']['id']
                    messages.append({'role': 'tool', 'tool_call_id': request['id'], 'content': json.dumps(result)})
            else:
                if controller.state != 'running': break
                gen = policy.responses(response['content']); event = next(gen)
                while 'tool' in event:
                    event = gen.send(call('user', event['tool'], event['arguments']))
                messages.append({'role': 'user', 'content': event['content']})
        else:
            raise RuntimeError('Controller exceeded offline probe limit')
        controller.thread.join(timeout=2)
        if controller.thread.is_alive(): raise RuntimeError('Controller worker did not terminate')
    finally:
        service.stdin.write('null\n'); service.stdin.flush(); service.stdin.close(); service.wait(timeout=30)
        if service.returncode: raise RuntimeError('Native public service failed')
    outcome = {'task_id': task, 'variant': variant, 'controller_state': controller.state,
               'reason': controller.reason, 'assistant_user_role_calls': 0, 'real_model_calls': 0,
               'grader_called_by_controller': False, 'shifted_from_id': original_id, 'actual_proposal_id': actual_id}
    if variant == 'id_shift': assert shift and original_id != actual_id
    output.mkdir(parents=True, exist_ok=True)
    (output / 'controller.json').write_text(json.dumps(outcome, indent=2), encoding='utf-8')
    (output / 'public-dialogue.json').write_text(json.dumps(messages, indent=2), encoding='utf-8')
    return outcome


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--variants', nargs='+', default=['baseline', 'paraphrase', 'pending_once', 'clarify_once', 'id_shift', 'decline_first', 'forged_approval', 'stale_approval', 'missing_files', 'no_update', 'changed_facts'])
    args = p.parse_args()
    if args.output.exists(): raise FileExistsError('Preserve previous attempts')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    rows = []
    for variant in args.variants:
        for task in ('case_040', 'case_031', 'case_001', 'case_049', 'case_036'):
            if variant == 'missing_files' and task not in ('case_001', 'case_031'): continue
            if variant == 'no_update' and task == 'case_049': continue
            if variant == 'changed_facts' and task != 'case_001': continue
            outcome = run(task, variant, args.source_dir, args.output / variant / task, root)
            rows.append(outcome)
            print(task, variant, outcome['controller_state'], outcome['reason'][:160], flush=True)
    (args.output / 'summary.json').write_text(json.dumps({'kind': 'adaptive_offline_controls_not_live_llm', 'tasks': rows}, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
