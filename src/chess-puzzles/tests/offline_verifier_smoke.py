"""Real Docker grading controls, without model APIs. Add --full for all 100 CLI oracles."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from chess_puzzles.adapter import ChessPuzzlesAdapter
from chess_puzzles.source import prepare_source


def run_oracle(dataset, folder, expected):
    folder.mkdir(parents=True)
    config = {
        'job_name': 'oracle', 'jobs_dir': str(folder.resolve()),
        'n_attempts': 1, 'n_concurrent_trials': 4, 'quiet': True,
        'retry': {'max_retries': 0},
        'environment': {'type': 'docker', 'delete': True},
        'datasets': [{'path': str(dataset.resolve())}],
        'agents': [{'name': 'oracle'}],
    }
    config_path = folder / 'config.json'
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    env = os.environ.copy()
    for key in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CHESS_PUZZLES_WORKER_KEY'):
        env.pop(key, None)
    with (folder / 'console.log').open('w') as log:
        subprocess.run([str(Path(sys.executable).with_name('harbor')), 'run', '-c', str(config_path)],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    files = sorted((folder / 'oracle').glob('*/result.json'))
    assert len(files) == len(expected), (folder, len(files), len(expected))
    results = []
    for path in files:
        trial = json.loads(path.read_text())
        name = trial['task_name']
        assert name in expected, (path, name)
        assert trial['exception_info'] is None, (path, trial['exception_info'])
        assert trial['verifier_environment_mode'] == 'separate', path
        reward = trial['verifier_result']['rewards']['reward']
        assert reward == expected[name], (path, reward, expected[name])
        grading = json.loads((path.parent / 'verifier/result.json').read_text())
        answer_path = path.parent / 'artifacts/app/answer.txt'
        if grading['status'] == 'missing_answer':
            assert not answer_path.exists(), path
        else:
            assert answer_path.read_text() == grading['answer'], path
        results.append({'task_name': name, 'reward': reward, 'exception': None,
                        'verifier_mode': 'separate', 'grading': grading,
                        'artifact_retained': answer_path.exists(), 'result': str(path)})
    assert {r['task_name'] for r in results} == set(expected), folder
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    root = Path('jobs') / ('separate-verifier-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True)
    csv = prepare_source() / 'bench/task/chess_puzzles/puzzles.csv'
    results = []
    for variant in ('original', 'cli'):
        for case in ('correct', 'wrong', 'missing'):
            dataset = root / f'{variant}-{case}-tasks'
            task, = ChessPuzzlesAdapter(dataset, data_path=csv, variant=variant, task_ids=['4']).run()
            # These are disposable controls. The benchmark's templates remain unchanged.
            # Prove that the agent starts without the grader/gold, and that writes in its
            # /tests and unrelated /app files cannot replace or enter the fresh verifier.
            solve_path = task / 'solution/solve.sh'
            solve = solve_path.read_text()
            solve = solve.replace('set -euo pipefail',
                                  'set -euo pipefail\ntest ! -e /tests/record.json\ntest ! -e /tests/grade.py')
            solve += '\nmkdir -p /tests\nprintf "raise RuntimeError(\\\"agent grader leaked\\\")\\n" > /tests/grade.py\n'
            solve += 'printf "agent only\\n" > /app/untransferred-marker\n'
            if case == 'wrong':
                solve += "printf 'a1a1\\n' > /app/answer.txt\n"
            elif case == 'missing':
                solve += 'rm -f /app/answer.txt\n'
            solve_path.write_text(solve)
            # The test-only verifier assertion checks the boundary before normal grading.
            check = task / 'tests/test.sh'
            check.write_text(check.read_text().replace('set -euo pipefail',
                             'set -euo pipefail\ntest ! -e /app/untransferred-marker'))
            import tomllib
            name = tomllib.loads((task / 'task.toml').read_text())['task']['name']
            rows = run_oracle(dataset, root / f'{variant}-{case}', {name: int(case == 'correct')})
            row, = rows
            assert row['grading']['status'] == ('missing_answer' if case == 'missing' else 'scored')
            row.update(variant=variant, case=case, isolation_checks=True)
            results.append(row)
            print(json.dumps({'variant': variant, 'case': case, 'reward': row['reward']}), flush=True)
    if args.full:
        dataset = root / 'full-cli-tasks'
        tasks = ChessPuzzlesAdapter(dataset, data_path=csv, variant='cli').run()
        expected = {f'epoch-ai/chess-puzzles__{task.name}': 1 for task in tasks}
        rows = run_oracle(dataset, root / 'full-cli', expected)
        results.extend({**row, 'variant': 'cli', 'case': 'full-oracle'} for row in rows)
        print(f'Full CLI oracle: {len(rows)}/100, zero exceptions', flush=True)
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(root.glob('*-tasks/**/*')) if p.is_file()}
    summary = {'harbor_version': importlib.metadata.version('harbor'),
               'real_model_calls': 0, 'counts_as_parity': False,
               'task_files_sha256': hashes, 'results': results}
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(root / 'summary.json', flush=True)


if __name__ == '__main__':
    main()
