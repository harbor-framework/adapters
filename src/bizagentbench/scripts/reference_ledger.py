"""Inventory local attempts, including failures; never run or import a grader."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text('utf-8'))


def relative(path):
    return path.relative_to(ROOT).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    constructions = []
    for path in sorted((ROOT / 'validation/references').glob('*/case_*')):
        if path.parent.name == 'final50':  # Final check input is a copy, not another attempt.
            continue
        record = {'path': relative(path), 'task_id': path.name}
        for name, key in [('construction.json', 'construction'), ('construction-error.json', 'error')]:
            if (path / name).exists():
                record[key] = read(path / name)
        trace = read(path / 'public-tools.json') if (path / 'public-tools.json').exists() else []
        record['tool_calls_recorded'] = len(trace)
        record['terminal_outcome_recorded'] = bool(trace and trace[-1]['tool'] == 'record_case_outcome'
                                                 and trace[-1]['response']['ok'])
        if path.parent.name == 'attempt51' and path.name == 'case_009':
            record['diagnostic_note'] = ('Authoring loop did not stop when public wait returned no event; '
                                         'the two verified task-owned processes were stopped. '
                                         'The bounded-wait correction was verified in attempt53.')
        constructions.append(record)
    checks = [{'path': relative(path), **read(path)}
              for path in sorted((ROOT / 'validation').glob('reference-check*/summary.json'))]
    native = []
    for path in sorted((ROOT / 'validation').glob('native-reference-batch*/native-batch.json')):
        native.append({'path': relative(path), **read(path)})
    harbor = []
    for job in sorted((ROOT / 'validation/harbor').glob('scripted-*')):
        result = read(job / 'result.json')
        row = {'path': relative(job), 'finished_at': result['finished_at'],
               'completed': result['stats']['n_completed_trials'],
               'errored': result['stats']['n_errored_trials'], 'trials': []}
        for path in sorted(job.glob('*/result.json')):
            trial = read(path)
            record = {'path': relative(path.parent), 'task_name': trial['task_name'],
                      'verifier_environment_mode': trial.get('verifier_environment_mode'),
                      'verifier_result': trial.get('verifier_result'),
                      'exception_info': trial.get('exception_info')}
            error = path.parent / 'verifier/error.json'
            if error.exists():
                record['verifier_error'] = read(error)
            row['trials'].append(record)
        harbor.append(row)
    output = {'kind': 'offline_diagnostic_attempt_inventory_not_model_sampling',
              'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'construction_attempts': constructions, 'isolated_checks': checks,
              'native_batches': native, 'harbor_jobs': harbor,
              'notes': ['All existing failed attempts are retained locally.',
                        'final50 is a copy of explicitly selected constructions, not a new attempt.',
                        'Cases 021 and 030 each retain a failed Harbor verifier run and a named retry after JSON normalization.',
                        'No model scores, real-LLM acceptance rate or statistical parity are inferred.']}
    args.output.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(f'Inventoried {len(constructions)} constructions, {len(checks)} isolated check batches, '
          f'{len(native)} native batches, {len(harbor)} Harbor jobs.')


if __name__ == '__main__':
    main()
