"""Audit explicitly selected offline controls without importing a native grader.

Run only after construction checks, native runs, and Harbor separate verifiers
finish. Missing evidence fails closed; retries must be named in the selection.
Paths in the selection and report are relative to the adapter directory.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SUCCESS_KEYS = ('goal_success', 'process_success', 'protection_success', 'strict_success')


def read(path):
    return json.loads(path.read_text('utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(row):
    task = row['task_id']
    reference = ROOT / row['reference']
    trace_path = reference / 'public-tools.json'
    trace = read(trace_path)
    construction = read(reference / 'construction.json')
    require(construction['task_id'] == task, f'{task}: construction identity')
    require(construction['live_llm_verified'] is False, f'{task}: misleading model claim')
    require(construction['score_available_to_planner'] is False, f'{task}: grader boundary')
    require(trace[-1]['tool'] == 'record_case_outcome' and trace[-1]['response']['ok'],
            f'{task}: unfinished public construction')
    check_path = ROOT / row['construction_check']
    check = read(check_path)
    require(all(check[key] is True for key in SUCCESS_KEYS), f'{task}: construction failed')
    native_path = ROOT / row['native_result']
    native = read(native_path)
    require(native['task_id'] == task, f'{task}: native identity')
    require(native['reward'] == 1.0 and native['termination'] == 'user_stop',
            f'{task}: unsuccessful or incomplete native episode')
    require(all(native['verification'][key] is True for key in SUCCESS_KEYS),
            f'{task}: native business checks failed')
    job = ROOT / row['harbor_job']
    job_result = read(job / 'result.json')
    require(bool(job_result['finished_at']), f'{task}: Harbor job still running')
    candidates = []
    for path in job.glob('*/artifacts/private/runs/evidence.json'):
        evidence = read(path)
        if evidence['task_id'] == task:
            candidates.append((path, evidence))
    require(len(candidates) == 1, f'{task}: missing/duplicate evidence in explicit job')
    evidence_path, evidence = candidates[0]
    for key in ('task_id', 'reward', 'termination', 'actual_tool_calls', 'classification', 'verification'):
        require(native[key] == evidence['result'][key], f'{task}: native/Harbor mismatch: {key}')
    trial = evidence_path.parents[3]
    trial_result = read(trial / 'result.json')
    require(trial_result.get('exception_info') is None, f'{task}: Harbor trial exception')
    require(trial_result.get('verifier_environment_mode') == 'separate',
            f'{task}: Harbor did not use the separate verifier')
    verifier_path = trial / 'verifier/result.json'
    verifier = read(verifier_path)
    require(verifier['task_id'] == task and verifier['verification'] == native['verification'],
            f'{task}: isolated grader full-verdict mismatch')
    require(verifier['reward'] == native['reward'] == float((trial / 'verifier/reward.txt').read_text()),
            f'{task}: isolated grader reward mismatch')
    require(not (trial / 'verifier/reward.json').exists(), f'{task}: alternate reward survived')
    require(not (trial / 'verifier/error.json').exists(), f'{task}: verifier error')
    dataset = ROOT / row['dataset_task']
    source = read(dataset / 'source.json')
    require(source['task_id'] == task and source['commit'] == evidence['upstream_commit']
            and source['archive_sha256'] == evidence['archive_sha256'],
            f'{task}: source identity differs from collected evidence')
    config = tomllib.loads((dataset / 'task.toml').read_text('utf-8'))
    require(config['verifier']['environment_mode'] == 'separate', f'{task}: shared grader')
    require(digest(dataset / 'environment/runtime/public-tools.json') == digest(trace_path),
            f'{task}: packaged trace differs from selected construction')
    # Explicitly retain the initial infrastructure failure when selecting a retry.
    prior = []
    if row.get('superseded_harbor_job'):
        for path in (ROOT / row['superseded_harbor_job']).glob('*/artifacts/private/runs/evidence.json'):
            if read(path)['task_id'] == task:
                error_path = path.parents[3] / 'verifier/error.json'
                prior.append({'trial': relative(path.parents[3]), 'verifier_error': read(error_path)})
        require(len(prior) == 1 and row.get('rerun_reason'), f'{task}: undocumented retry')
    hashes = {name: digest(path) for name, path in {
        'public_tools': trace_path, 'construction_check': check_path,
        'constructed_world': reference / 'world.json',
        'construction_metadata': reference / 'construction.json',
        'native_result': native_path, 'harbor_evidence': evidence_path,
        'isolated_verifier_result': verifier_path, 'task_toml': dataset / 'task.toml',
        'packaged_grader': dataset / 'tests/grade.py',
        'packaged_scripted_provider': dataset / 'environment/runtime/reference_provider.py',
        'packaged_source_identity': dataset / 'source.json',
    }.items()}
    return {
        **row, 'harbor_trial': relative(trial), 'hashes_sha256': hashes,
        'upstream_commit': source['commit'], 'upstream_archive_sha256': source['archive_sha256'],
        'construction_tool_calls': len(trace), 'tool_calls': native['actual_tool_calls'],
        'native_reward': native['reward'], 'harbor_reward': verifier['reward'],
        'termination': native['termination'], 'classification': native['classification'],
        'construction_checks': {key: check[key] for key in SUCCESS_KEYS},
        'full_verdict_equal': True, 'separate_grader': True, 'live_llm_verified': False,
        'superseded_attempts': prior,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selection = read(args.selection)
    rows = selection['tasks']
    require(sorted(row['task_id'] for row in rows) == [f'case_{n:03}' for n in range(1, 51)],
            'Selection must contain each of the 50 cases exactly once')
    audited = [audit(row) for row in rows]
    report = {
        'kind': 'offline_trajectory_equivalence_not_model_parity',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'selection_sha256': digest(args.selection),
        'coverage': {'constructed': 50, 'isolated_construction_pass': 50,
                     'native_scripted_pass': 50, 'harbor_scripted_pass': 50,
                     'full_verdict_matches': 50, 'live_llm_verified': 0, 'model_parity_runs': 0},
        'tasks': audited,
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('50/50 complete native/Harbor verdicts and separate grader rewards matched; live LLM: 0.')


if __name__ == '__main__':
    main()
