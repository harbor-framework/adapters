"""Run disposable real-Harbor security trials; no model or real API key is used.

Source task sets must be generated separately with public and no-network profiles.
Diagnostic copies replace Oracle solve.sh with attacks, or start a local fake judge.
The original generated tasks and adapter scoring code are never overwritten.
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from docker_review import IDS, SERVER


def prepare(public: Path, offline: Path, destination: Path, manifest: list[dict]):
    urls = {row['task_id']: row for row in manifest}
    expected = {}
    for profile, source in (('public', public), ('offline', offline)):
        cases = ('tamper', 'symlink', 'network')
        if profile == 'offline':
            cases += ('tie', 'error', 'malformed')
        for tid in IDS:
            original = source / tid
            names = tomllib.loads((original / 'task.toml').read_text())['metadata']['gdpval_deliverable_filenames']
            for case in cases:
                label = f'{profile}-{case}-{tid}'
                task = destination / label
                shutil.copytree(original, task)
                config = (task / 'task.toml').read_text()
                config = config.replace(f'openai/gdpval__{tid}', f'openai/gdpval__{label}')
                (task / 'task.toml').write_text(config)
                script = '#!/bin/bash\nset -eu\nmkdir -p /app /logs/artifacts\n'
                reward = 0
                if case == 'tamper':
                    # Agent owns its container, but none of this state may grade it.
                    script += r'''
mkdir -p /logs/verifier /tests /tmp/poison
printf '{"reward":1}' > /logs/verifier/reward.json
printf 'raise RuntimeError("agent sitecustomize executed")\n' > /tmp/poison/sitecustomize.py
printf 'raise RuntimeError("agent litellm executed")\n' > /app/litellm.py
printf 'OPENAI_BASE_URL=http://127.0.0.1:1\nJUDGE_MODEL=agent-controlled\n' >> /etc/environment
rm /usr/local/bin/python3
printf '#!/bin/sh\nmkdir -p /logs/verifier\nprintf 1 > /logs/verifier/reward.txt\nexit 0\n' > /usr/local/bin/python3
chmod +x /usr/local/bin/python3
nohup sh -c 'while :; do printf "{\"reward\":1}" > /logs/verifier/reward.json; sleep 0.02; done' >/tmp/poison/writer.log 2>&1 &
printf '{"runtime_replaced":true,"background_reward_writer":true}' > /logs/artifacts/security.json
'''
                elif case == 'symlink':
                    script += '\n'.join('ln -s ' + shlex.quote('/tests/gold/' + name) + ' ' + shlex.quote('/app/' + name) for name in names) + '\n'
                elif case == 'network':
                    code = '''import hashlib,json,socket,subprocess,urllib.request
from pathlib import Path
row = ROW
result = {'interfaces': socket.if_nameindex(), 'routes': Path('/proc/net/route').read_text()}
for command in (['iptables','-P','OUTPUT','ACCEPT'], ['ip6tables','-P','OUTPUT','ACCEPT']):
    p = subprocess.run(command,capture_output=True,text=True)
    result[command[0]] = {'exit_code': p.returncode, 'stderr': p.stderr}
try:
    socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    result['raw_socket'] = 'opened'
except OSError as exc: result['raw_socket'] = type(exc).__name__
try:
    with socket.create_connection(('1.1.1.1',443),timeout=3): result['direct_ip'] = 'connected'
except OSError as exc: result['direct_ip'] = type(exc).__name__
try:
    data = urllib.request.urlopen(row['url'],timeout=10).read()
    result['gold_download'] = {'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data)}
except OSError as exc: result['gold_download'] = {'error':type(exc).__name__}
Path('/logs/artifacts/security.json').write_text(json.dumps(result,indent=2))
'''.replace('ROW', repr(urls[tid]))
                    script += "python3 -I - <<'PYPROBE'\n" + code + '\nPYPROBE\n'
                else:
                    # Valid artifacts follow the unchanged non-exact-match route.
                    # Server output is fixed: it tests transport, never quality.
                    script = (task / 'solution/solve.sh').read_text()
                    code = '\n'.join(f"p=Path('/app')/{name!r};p.write_bytes(p.read_bytes()+b'\\n')" for name in names)
                    script += "\npython3 -I - <<'PYARTIFACT'\nfrom pathlib import Path\n" + code + '\nPYARTIFACT\n'
                    (task / 'tests/local_judge.py').write_text(SERVER)
                    test = (task / 'tests/test.sh').read_text()
                    prefix = f"mkdir -p /review\nprintf %s {shlex.quote(case)} > /review/mode\npython3 -I /tests/local_judge.py >/tmp/local-judge.log 2>&1 &\n"
                    # The service must listen before LiteLLM sends its first request.
                    prefix += "python3 -I -c 'import socket,time;\nfor _ in range(100):\n try:\n  socket.create_connection((\"127.0.0.1\",3000),timeout=.1).close();break\n except OSError: time.sleep(.05)\nelse: raise RuntimeError(\"local judge not ready\")'\n"
                    (task / 'tests/test.sh').write_text(test.replace('set -euo pipefail\n', 'set -euo pipefail\n' + prefix, 1))
                    config = (task / 'task.toml').read_text().replace('[verifier.env]\n', '[verifier.env]\nOPENAI_API_KEY = "local-dummy"\nOPENAI_BASE_URL = "http://127.0.0.1:3000/v1"\n')
                    (task / 'task.toml').write_text(config)
                    reward = .5 if case == 'tie' else None
                (task / 'solution/solve.sh').write_text(script)
                expected[label] = {'reward': reward, 'profile': profile, 'case': case, 'task_id': tid}
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-tasks', type=Path, required=True)
    parser.add_argument('--offline-tasks', type=Path, required=True)
    parser.add_argument('--gold-manifest', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true', help='Check a completed attempt without rerunning it')
    args = parser.parse_args()
    if not args.check_only:
        args.artifacts.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.gold_manifest.read_text())
    tasks = args.artifacts / 'tasks'
    if args.check_only:
        expected = json.loads((args.artifacts / 'expected.json').read_text())
    else:
        expected = prepare(args.public_tasks, args.offline_tasks, tasks, manifest)
        (args.artifacts / 'expected.json').write_text(json.dumps(expected, indent=2))
    command = [sys.executable, '-m', 'harbor.cli.main', 'run', '-p', str(tasks), '-a', 'oracle', '-n', '3', '--max-retries', '0', '--jobs-dir', str(args.artifacts / 'jobs'), '--job-name', 'security']
    # Use the installed entrypoint, in the same isolated uv environment as Python.
    command[:3] = ['harbor']
    if not args.check_only:
        with (args.artifacts / 'run.log').open('w') as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    records = []
    for path in (args.artifacts / 'jobs/security').glob('*/result.json'):
        data = json.loads(path.read_text())
        label = data['task_name'].split('gdpval__', 1)[1]
        record = {**expected[label], 'label':label, 'result':str(path), 'exception':data.get('exception_info'), 'verifier_result':data.get('verifier_result')}
        actual = data.get('verifier_result')
        if record['reward'] is None:
            assert actual is None and record['exception']['exception_type'] == 'RewardFileNotFoundError', record
            log = (path.parent / 'verifier/test-stdout.txt').read_text()
            assert ('local injected failure' if record['case'] == 'error' else 'Missing or invalid pairwise score') in log, record
        else:
            assert actual and actual['rewards']['reward'] == record['reward'], record
            assert record['exception'] is None, record
        if record['case'] == 'network':
            probe = json.loads((path.parent / 'artifacts/logs/artifacts/security.json').read_text())
            record['probe'] = probe
            assert probe['iptables']['exit_code'] != 0 and probe['ip6tables']['exit_code'] != 0
            assert probe['raw_socket'] != 'opened'
            if record['profile'] == 'offline':
                assert not any(name.startswith(('eth', 'en')) for _, name in probe['interfaces'])
                assert len(probe['routes'].strip().splitlines()) == 1
                assert probe['direct_ip'] != 'connected' and 'error' in probe['gold_download']
            else:
                source = next(row for row in manifest if row['task_id'] == record['task_id'])
                assert probe['gold_download']['sha256'] == source['sha256']
        records.append(record)
    assert len(records) == len(expected), (len(records), len(expected))
    (args.artifacts / 'report.json').write_text(json.dumps(records, indent=2))
    print(f'{len(records)} security assertions passed; local fake judge only.')


if __name__ == '__main__':
    main()
