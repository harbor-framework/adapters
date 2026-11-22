"""Post-run audit; execute ONLY in a separate offline grader container.

Calls the existing native checker after all controller processes have ended.
Never mount this program as an agent/controller asset.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--controls', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
if args.output.exists(): raise FileExistsError('Preserve earlier grading attempts')
args.output.mkdir(parents=True)
control = json.loads((args.controls / 'summary.json').read_text('utf-8'))['tasks']
assert len(control) == 47
expected = {'baseline', 'paraphrase', 'pending_once', 'clarify_once', 'id_shift'}
rows = []
for variant in sorted({r['variant'] for r in control}):
    target = args.output / variant
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('check_references.py')),
                             '--references', str(args.controls / variant), '--output', str(target)],
                            capture_output=True, text=True)
    (args.output / (variant + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    grades = json.loads((target / 'summary.json').read_text('utf-8'))['tasks']
    selected = [r for r in control if r['variant'] == variant]
    assert {r['task_id'] for r in grades} == {r['task_id'] for r in selected}
    assert result.returncode == (0 if variant in expected else 1)
    for item in selected:
        verdict = next(r for r in grades if r['task_id'] == item['task_id'])
        success = variant in expected
        assert (item['controller_state'] == 'completed') == success
        assert verdict['strict_success'] == success, (variant, item['task_id'], verdict)
        trace = json.loads((args.controls / variant / item['task_id'] / 'public-tools.json').read_text('utf-8'))
        assert not any(r['actor'] == 'assistant' and r['tool'] in ('get_my_requests', 'decide_request', 'wait_for_update', 'upload_file', 'list_my_files') for r in trace)
        completed = [r for r in trace if r['tool'] == 'record_case_outcome' and r['arguments'].get('outcome') == 'COMPLETED']
        assert bool(completed) == success
        rows.append({**item, 'native_verdict': verdict, 'correct_expected_branch': True,
                     'success_recorded': bool(completed), 'public_tool_calls': len(trace)})
    print(variant, len(selected), 'expected branches and independent grades matched', flush=True)
report = {'kind': 'adaptive_offline_controls_with_separate_grading_not_live_llm',
          'controls': rows, 'summary': {'total': len(rows), 'successful_flows': sum(r['success_recorded'] for r in rows),
                                      'safe_stops': sum(not r['success_recorded'] for r in rows),
                                      'all_expected_branches_matched': True, 'real_model_calls': 0}}
(args.output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report['summary']))
