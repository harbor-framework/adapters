"""Run original Inspect and real Docker/Harbor with scripted model responses; no API key."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from chess_puzzles.adapter import ChessPuzzlesAdapter
from chess_puzzles.parity import harbor_config, collect_harbor
from chess_puzzles.source import prepare_source


def main():
    root = Path('jobs') / ('offline-smoke-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True)
    source = prepare_source()
    dataset = root / 'tasks'
    ChessPuzzlesAdapter(dataset, data_path=source / 'bench/task/chess_puzzles/puzzles.csv',
                        task_ids=['1'], variant='original').run()
    env = os.environ.copy()
    env.pop('ANTHROPIC_API_KEY', None)
    env.pop('OPENAI_API_KEY', None)
    env.pop('CHESS_PUZZLES_WORKER_KEY', None)
    summaries = []
    for scenario in ('submit', 'continue', 'forced', 'wrong', 'compact', 'timeout'):
        folder = root / scenario
        folder.mkdir()
        settings = {'model': 'mockllm/model', 'base_url': None, 'source_dir': str(source),
                    'max_output_tokens': 100 if scenario == 'forced' else 20000,
                    'response_max_tokens': 1000,
                    'compaction_threshold_tokens': 1000 if scenario == 'compact' else 100000,
                    'attempt_timeout_sec': 1 if scenario == 'timeout' else 1800, 'mock_scenario': scenario}
        settings_file = folder / 'settings.json'
        settings_file.write_text(json.dumps(settings, indent=2))
        with (folder / 'original-console.log').open('w') as log:
            original_run = subprocess.run([sys.executable, '-m', 'chess_puzzles.original', '--settings', str(settings_file),
                            '--sample-id', '1', '--log-dir', str(folder / 'original')],
                           stdout=log, stderr=subprocess.STDOUT, check=False, env=env)
        assert (original_run.returncode != 0) == (scenario == 'timeout')
        config = harbor_config(settings, dataset, [1], folder, 'harbor')
        config_file = folder / 'harbor-config.json'
        config_file.write_text(json.dumps(config, indent=2))
        with (folder / 'harbor-console.log').open('w') as log:
            subprocess.run([str(Path(sys.executable).with_name('harbor')), 'run', '-c', str(config_file)],
                           stdout=log, stderr=subprocess.STDOUT, check=True, env=env)
        original = json.loads((folder / 'original/summary.json').read_text())
        if scenario == 'timeout':
            try:
                collect_harbor(folder / 'harbor', [1], simulated=True)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Harbor timeout was counted as a chess score')
            harbor = json.loads((folder / 'harbor/summary.json').read_text())
            for outcome in (original, harbor):
                assert outcome['status'] == 'incomplete'
                assert outcome['accuracy'] is None
                assert outcome['samples'][0]['reward'] is None
                assert outcome['samples'][0]['limit']['type'] == 'time'
            trials = list((folder / 'harbor').glob('*/result.json'))
            assert len(trials) == 1
            failure = json.loads(trials[0].read_text())['exception_info']
            assert failure['exception_type'] != 'AgentTimeoutError', failure
            summaries.append({'scenario': scenario, 'both_sides': 'incomplete (Inspect time limit)',
                              'simulated': True})
            print(summaries[-1], flush=True)
            continue
        harbor = collect_harbor(folder / 'harbor', [1], simulated=True)
        expected = 0 if scenario == 'wrong' else 1
        assert original['accuracy'] == harbor['accuracy'] == expected
        assert original['samples'][0]['metadata']['forced_final_answer'] == (scenario == 'forced')
        submitted = list((folder / 'harbor').glob('*/agent/submitted.json'))
        assert len(submitted) == 1
        submission = json.loads(submitted[0].read_text())
        assert submission['sample_metadata']['forced_final_answer'] == (scenario == 'forced')
        summaries.append({'scenario': scenario, 'original_reward': original['accuracy'],
                          'harbor_reward': harbor['accuracy'], 'simulated': True})
        print(summaries[-1], flush=True)
    (root / 'summary.json').write_text(json.dumps({'paid_api_calls': 0, 'results': summaries}, indent=2))
    print(root / 'summary.json')


if __name__ == '__main__':
    main()
