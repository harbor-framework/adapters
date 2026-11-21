"""Original + actual Harbor/Docker against a loopback Anthropic fake, no paid API.

The fake deliberately rejects count endpoints. Responses go through the real
Inspect provider, and Harbor runs its separate worker process and verifier.
"""
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from chess_puzzles.adapter import ChessPuzzlesAdapter
from chess_puzzles.parity import harbor_config, collect_harbor
from chess_puzzles.source import prepare_source, upstream
from fake_anthropic import FakeAnthropic


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        fake = self.server.fake
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        status, headers, content = fake.response(self.path, body)
        if fake.scenario == 'timeout':
            time.sleep(3)
        try:
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Expected when Inspect cancels the timeout scenario.


def main():
    stamp = datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y%m%d-%H%M%S')
    root = Path('jobs') / ('offline-local-count-' + stamp)
    root.mkdir(parents=True)
    source = prepare_source()
    sample = next(s for s in upstream(source).chess_puzzles(
        max_output_tokens=20000, compaction_threshold_tokens=200000).dataset if s.id == 4)
    dataset = root / 'tasks'
    ChessPuzzlesAdapter(dataset, data_path=source / 'bench/task/chess_puzzles/puzzles.csv',
                        task_ids=['4'], variant='original').run()
    env = os.environ.copy()
    for name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CHESS_PUZZLES_WORKER_KEY'):
        env.pop(name, None)
    env['ANTHROPIC_API_KEY'] = 'offline-local-count-not-a-real-key'
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        for scenario in ('submit', 'continue', 'forced', 'compact', 'error', 'timeout'):
            folder = root / scenario
            folder.mkdir()
            settings = {'model': 'anthropic/claude-haiku-5-5',
                        'base_url': f'http://127.0.0.1:{server.server_port}',
                        'source_dir': str(source), 'token_count_mode': 'local',
                        'max_output_tokens': 1 if scenario == 'forced' else 20000,
                        'response_max_tokens': 1000,
                        'compaction_threshold_tokens': 1500 if scenario == 'compact' else 200000,
                        'attempt_timeout_sec': 1 if scenario == 'timeout' else 30,
                        'reasoning_effort': None}
            settings_file = folder / 'settings.json'
            settings_file.write_text(json.dumps(settings, indent=2))
            requests = []
            for side in ('original', 'harbor'):
                fake = FakeAnthropic(scenario, sample.target)
                server.fake = fake
                if side == 'original':
                    command = [sys.executable, '-m', 'chess_puzzles.original', '--settings', str(settings_file),
                               '--sample-id', '4', '--log-dir', str(folder / side)]
                else:
                    config_file = folder / 'harbor-config.json'
                    config_file.write_text(json.dumps(harbor_config(settings, dataset, [4], folder, 'harbor'), indent=2))
                    command = [str(Path(sys.executable).with_name('harbor')), 'run', '-c', str(config_file)]
                with (folder / f'{side}-console.log').open('w') as log:
                    subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
                requests.append(list(fake.requests))
                (folder / f'{side}-requests.json').write_text(json.dumps(fake.requests, indent=2))
                assert fake.requests and all(r['path'] == '/v1/messages' for r in fake.requests), folder
            original = json.loads((folder / 'original/summary.json').read_text())
            try:
                harbor = collect_harbor(folder / 'harbor', [4], simulated=True)
            except RuntimeError:
                harbor = json.loads((folder / 'harbor/summary.json').read_text())
            assert requests[0] == requests[1], folder
            expected_status = 'incomplete' if scenario in ('error', 'timeout') else 'complete'
            assert original['status'] == harbor['status'] == expected_status, folder
            if expected_status == 'complete':
                assert original['accuracy'] == harbor['accuracy'] == 1, folder
                trial_path = Path(harbor['samples'][0]['result'])
                trial = json.loads(trial_path.read_text())
                assert trial['verifier_environment_mode'] == 'separate', folder
                assert (trial_path.parent / 'artifacts/app/answer.txt').read_text() == harbor['samples'][0]['answer'], folder
                assert bool(original['samples'][0]['compactions']) == (scenario == 'compact')
                assert bool(harbor['samples'][0]['compactions']) == (scenario == 'compact')
                for row in (original['samples'][0], harbor['samples'][0]):
                    assert row['metadata']['forced_final_answer'] == (scenario == 'forced')
            else:
                assert original['accuracy'] is None and harbor['accuracy'] is None
                assert original['samples'][0]['status'] == harbor['samples'][0]['status']
            result = {'scenario': scenario, 'status_both': expected_status,
                      'requests_identical': True, 'count_endpoint_requests': 0,
                      'message_requests_per_side': len(requests[0]), 'simulated': True}
            if expected_status == 'complete':
                result['verifier_mode'] = 'separate'
                result['submitted_answer_retained'] = True
            results.append(result)
            print(json.dumps(result), flush=True)
    finally:
        server.shutdown()
        server.server_close()
        (root / 'summary.json').write_text(json.dumps({
            'real_model_calls': 0, 'counts_as_parity': False, 'results': results,
        }, indent=2) + '\n')
    print(root / 'summary.json')


if __name__ == '__main__':
    main()
