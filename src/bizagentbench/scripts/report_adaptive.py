"""Read-only consolidation of adaptive controls and full-run evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TASKS = {'case_001', 'case_031', 'case_036', 'case_040', 'case_049'}


def read(path): return json.loads(path.read_text('utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def relative(path): return path.relative_to(ROOT).as_posix()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    job = ROOT / 'validation/harbor/adaptive-final-v2'
    summary = read(job / 'result.json')
    assert summary['finished_at'] and summary['stats']['n_completed_trials'] == 5 and summary['stats']['n_errored_trials'] == 0
    rows = []
    for path in sorted(job.glob('*/artifacts/private/runs/evidence.json')):
        evidence = read(path); task = evidence['task_id']; trial = path.parents[3]
        native_path = ROOT / f'validation/adaptive-native-final/{task}__trial0/result.json'
        native = read(native_path)
        for key in ('task_id', 'reward', 'termination', 'classification', 'actual_tool_calls', 'verification'):
            assert native[key] == evidence['result'][key], (task, key)
        verifier = read(trial / 'verifier/result.json')
        assert verifier['verification'] == native['verification']
        assert verifier['reward'] == native['reward'] == float((trial / 'verifier/reward.txt').read_text()) == 1.0
        assert read(trial / 'result.json')['verifier_environment_mode'] == 'separate'
        assert not (trial / 'verifier/reward.json').exists() and not (trial / 'verifier/error.json').exists()
        dataset = ROOT / '../../../datasets/bizagentbench-adaptive-final-v2' / ('bizagentbench-' + task.replace('_', '-'))
        for name in ('adaptive.py', 'adaptive_plans.py'):
            assert sha(dataset / 'solution/bizagentbench' / name) == sha(ROOT / 'src/bizagentbench' / name)
        assert sha(dataset / 'solution/adaptive_run.py') == sha(ROOT / 'src/bizagentbench/adaptive_run.py')
        assert not list((dataset / 'solution').rglob('adaptive_customer.py'))
        assert not list((dataset / 'solution').rglob('grade.py'))
        rows.append({'task_id': task, 'reward': 1.0, 'tool_calls': native['actual_tool_calls'],
                     'full_native_harbor_verdict_equal': True, 'separate_grader': True,
                     'native_result': relative(native_path), 'harbor_trial': relative(trial),
                     'hashes_sha256': {'native_result': sha(native_path), 'harbor_evidence': sha(path),
                                       'separate_verdict': sha(trial / 'verifier/result.json')}})
    assert {r['task_id'] for r in rows} == TASKS and len(rows) == 5
    controls = read(ROOT / 'validation/adaptive-controls-grader-final/summary.json')
    assert controls['summary'] == {'total': 47, 'successful_flows': 25, 'safe_stops': 22,
                                  'all_expected_branches_matched': True, 'real_model_calls': 0}
    suite = ET.parse(ROOT / 'validation/unit-adaptive-linux.xml').getroot().find('testsuite')
    assert suite is not None and int(suite.attrib['tests']) == 79 and int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
    report = {'kind': 'adaptive_reference_offline_validation_not_live_llm_or_model_parity',
              'supported_tasks': sorted(TASKS), 'full_run_comparisons': rows, 'variation_controls': controls['summary'],
              'variation_evidence': 'validation/adaptive-controls-grader-final/summary.json',
              'tests': {'passed': 79, 'failed': 0, 'platform': 'Linux', 'junit': 'validation/unit-adaptive-linux.xml'},
              'live_model_calls': 0, 'live_customer_validated': False, 'model_parity_runs': 0,
              'controller_scope': 'Five business-specific plans; structured customer receipts and bounded clarification. Not arbitrary natural-language planning or support for all 50 cases.',
              'prior_attempts': [
                  {'path': 'validation/adaptive-controls-attempt01', 'reason': 'Case 036 checked a nonexistent refund flag and safely halted. Corrected using public refund_received_minor and fee fields.'},
                  {'path': 'validation/adaptive-controls-attempt02', 'reason': 'Intermediate controls before stronger recipient-verification gate and clearer FX-fill error.'},
                  {'path': 'validation/adaptive-native-attempt01', 'reason': 'Earlier full native diagnostic before the final public-recipient check.'},
                  {'path': 'validation/harbor/adaptive-final', 'reason': 'Offline fixture evaluated a nonexistent shallow parent path during import. Packaged import failed; fixed and retained all original trials.'}],
              'approval_boundary': 'Customer reports cannot authorize writes; native engine rejects forged/pending approval. No user-role tools are emitted by the assistant.',
              'source_files_sha256': {str(path.relative_to(ROOT)).replace('\\', '/'): sha(path)
                                      for path in [ROOT / 'src/bizagentbench/adaptive.py', ROOT / 'src/bizagentbench/adaptive_plans.py',
                                                   ROOT / 'src/bizagentbench/adaptive_run.py', ROOT / 'tests/fixtures/adaptive_customer.py',
                                                   ROOT / 'tests/fixtures/adaptive_provider.py', ROOT / 'tests/test_adaptive.py']}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('5 complete native/Harbor verdicts match; 25 successful variation flows, 22 safe stops, 79 tests; real models: 0.')


if __name__ == '__main__': main()
