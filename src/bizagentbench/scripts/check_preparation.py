"""Read-only validation of a disabled experiment draft; never launches a model."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


def validate_draft(plan, model, selection):
    execution = plan['execution']
    if execution['enabled'] is not False or execution['user_authorized'] is not False:
        raise ValueError('This offline preparation requires execution disabled and no user authorization.')
    if execution['authorized_spend_usd'] != 0:
        raise ValueError('No spending is authorized in this preparation.')
    if execution['concurrency'] != 1 or execution['automatic_job_retries'] != 0:
        raise ValueError('Keep serial trials and no automatic job retries in the proposed pilot.')
    ids = [r['task_id'] for r in selection['tasks']]
    if len(ids) != 10 or len(set(ids)) != 10:
        raise ValueError('The representative set must have 10 distinct cases.')
    if plan['phases'][0]['tasks'] != ids[:5] or plan['phases'][1]['tasks'] != ids[5:]:
        raise ValueError('Phase task order differs from the frozen selection.')
    for role in ('agent', 'user'):
        settings = model[role]
        if any(key in settings for key in ('api_key', 'dummy_api_key')):
            raise ValueError('Do not embed credentials.')
        host = urlsplit(settings['base_url']).hostname or ''
        if not host.endswith('.invalid') or not settings['model'].startswith('UNSET_APPROVED_DATED_'):
            raise ValueError('Draft endpoints and models must remain non-executable placeholders.')
    if model['episode_timeout_seconds'] != 5400 or model['max_errors'] != 16:
        raise ValueError('Native episode defaults changed without an explicit matched revision.')
    phases = plan['phases']
    if phases[-1]['run_order'] != ['native_r1', 'harbor_r1', 'native_r2', 'harbor_r2', 'native_r3', 'harbor_r3']:
        raise ValueError('Full parity runs must progress symmetrically.')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def read(name): return json.loads((args.root / 'preparation' / name).read_text('utf-8'))
    plan, model, selection = read('experiment-plan.json'), read('model.draft.json'), read('first-batch.json')
    validate_draft(plan, model, selection)
    model_path = args.root / plan['configuration']['model_config']
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != plan['configuration']['model_config_sha256']:
        raise ValueError('Model configuration changed after draft selection.')
    oracle_path = args.root / plan['configuration']['oracle_model_config']
    oracle = json.loads(oracle_path.read_text('utf-8'))
    if hashlib.sha256(oracle_path.read_bytes()).hexdigest() != plan['configuration']['oracle_model_config_sha256']:
        raise ValueError('Oracle configuration changed after drafting.')
    if oracle['user'] != model['user']:
        raise ValueError('Oracle and parity customer drafts must agree.')
    if oracle['agent']['model'] != 'UNIMPLEMENTED_PUBLIC_RESPONSE_REFERENCE_CONTROLLER':
        raise ValueError('Do not silently replace the oracle controller with a paid assistant model.')
    for row in selection['tasks']:
        trace = args.root / row['reference'] / 'public-tools.json'
        if hashlib.sha256(trace.read_bytes()).hexdigest() != row['public_trace_sha256']:
            raise ValueError('Selected reference changed: ' + row['task_id'])
    audit = read('adaptability-report.json')
    consent = read('consent-probe-summary.json')
    if audit['summary']['tasks'] != 50 or consent['probes_passed'] != 20:
        raise ValueError('Offline preparation evidence is incomplete.')
    replay = args.root / 'src/bizagentbench/task-template/solution/replay.py'
    if audit['replay_sha256'] != hashlib.sha256(replay.read_bytes()).hexdigest():
        raise ValueError('The audited replay program has changed.')
    public_results = args.root / consent['native_public_results']
    if hashlib.sha256(public_results.read_bytes()).hexdigest() != consent['native_public_results_sha256']:
        raise ValueError('Public consent evidence has changed.')
    probes = json.loads(public_results.read_text('utf-8'))['probes']
    if len(probes) != 20 or not all(p['unapproved_execution_rejected'] and not p['public_response']['ok'] for p in probes):
        raise ValueError('Consent boundary evidence does not show 20 rejected executions.')
    selected_ids = {r['task_id'] for r in selection['tasks']}
    for record in consent['isolated_grading']:
        path = args.root / record['summary_path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['summary_sha256']:
            raise ValueError('Separate grader evidence has changed.')
        grades = json.loads(path.read_text('utf-8'))['tasks']
        if {r['task_id'] for r in grades} != selected_ids or any(r['strict_success'] for r in grades):
            raise ValueError('Partial control incorrectly received success or task coverage differs.')
    report = {'kind': 'offline_preparation_readiness_not_execution_approval',
              'offline_preparation_complete': True, 'live_launch_ready': False,
              'live_calls_made': 0, 'authorized_spend_usd': 0,
              'blockers': [
                  'Current linear replay ignores customer/tool feedback; build and qualify a public-response adaptive reference controller.',
                  'Exact dated models, provider endpoints, provider limits and approved spending ceiling are not selected.',
                  'Installed Harbor wheel has no verified Git source SHA; freeze an approved source revision.',
                  'Freeze the adapter/controller source revision and evidence identity for the future experiment.',
                  'Obtain a new explicit user confirmation before any real model invocation.',
                  'Coordinate the matched parity plan before the separate parity phase.'],
              'scope_note': 'Exit 0 means the disabled preparation draft is consistent, never permission to launch.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Offline preparation is consistent. LIVE LAUNCH BLOCKED; approved spend $0; no model calls.')


if __name__ == '__main__':
    main()
