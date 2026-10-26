"""Historical shared-container diagnostics; not current isolation acceptance.

Use security_review.py for real Harbor separate-verifier regression.
Only a local fake judge is called; never a model.

Run from the repository root with the adapter uv environment. Artifacts are local.
The fake judge checks transport and score handling, not semantic grading quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

IDS = (
    '0112fc9b-c3b2-4084-8993-5a4abb1f54f1',
    '01d7e53e-0513-4109-a242-8ccaf442cd21',
    '02aa1805-c658-4069-8a6a-02dec146063a',
)
SERVER = r'''
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with Path('/review/requests.jsonl').open('a') as stream:
            stream.write(json.dumps(request) + '\n')
        mode = Path('/review/mode').read_text().strip()
        if mode == 'error':
            self.send_response(401); self.end_headers()
            self.wfile.write(b'{"error":{"message":"local injected failure","type":"authentication_error"}}')
            return
        content = '{}' if mode == 'malformed' else json.dumps({'winner': mode})
        body = json.dumps({'id':'local-review', 'object':'chat.completion',
            'created':0, 'model':'gpt-5', 'choices':[{'index':0,
            'message':{'role':'assistant','content':content}, 'finish_reason':'stop'}],
            'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
HTTPServer(('127.0.0.1',3000), Handler).serve_forever()
'''


def run(args, *, check=True, **kwargs):
    return subprocess.run(args, check=check, text=True, capture_output=True, timeout=700, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks-root', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--expect', choices=('upstream', 'hardened'), default='hardened')
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    report = []
    for tid in IDS:
        task = args.tasks_root.resolve() / tid
        destination = args.artifacts / tid
        destination.mkdir(exist_ok=True)
        names = tomllib.loads((task / 'task.toml').read_text())['metadata']['gdpval_deliverable_filenames']
        tag = f'gdpval-review:{tid}'
        build = run(['docker', 'build', '-t', tag, str(task / 'environment')], check=False)
        (destination / 'build.log').write_text(build.stdout + build.stderr)
        if build.returncode:
            raise RuntimeError(f'Build failed: {destination}')
        record = {'task_id':tid, 'deliverables':names, 'cases':{}}
        container = run(['docker','run','-d','--cap-add','NET_ADMIN',tag]).stdout.strip()
        def execute(command, *, check=True, container=container):
            return run(['docker','exec',container,'bash','-c',command],check=check)
        def python(code, container=container):
            return run(['docker','exec',container,'python3','-I','-c',code])
        def case(label, setup, mode='gold', destination=destination, record=record, tid=tid):
            python("from pathlib import Path; Path('/review/mode').write_text(" + repr(mode) + ")")
            python('import shutil; from pathlib import Path; shutil.rmtree("/app",ignore_errors=True); Path("/app").mkdir()\n' + setup)
            outcome = execute('OPENAI_API_KEY=local-dummy OPENAI_BASE_URL=http://127.0.0.1:3000/v1 bash /tests/test.sh', check=False)
            (destination / f'{label}.log').write_text(outcome.stdout + outcome.stderr)
            status = json.loads(python("import json; from pathlib import Path; print(json.dumps({n: Path('/logs/verifier',n).read_text() if Path('/logs/verifier',n).exists() else None for n in ('reward.txt','reward.json','error.json','rubric_judge.json')}))").stdout)
            status['exit_code'] = outcome.returncode
            record['cases'][label] = status
            print(tid, label, outcome.returncode, status['reward.txt'], flush=True)
        try:
            # Before uploading any tests or solution, inspect the real agent surface.
            before = python("import json,os; from pathlib import Path; print(json.dumps({'uid':os.getuid(),'tests_present':Path('/tests').exists(),'solution_present':Path('/solution').exists(),'reference_files':[str(p) for p in Path('/workspace/reference_files').rglob('*') if p.is_file()], 'python_writable':os.access('/usr/local/bin/python3',os.W_OK)}))")
            record['before_agent'] = json.loads(before.stdout)
            record['iptables'] = execute('iptables -S OUTPUT').stdout
            record['image'] = json.loads(run(['docker','image','inspect',tag,'--format','{{json .}}']).stdout)['Id']
            execute('mkdir -p /review /logs/verifier')
            server = destination / 'server.py'
            server.write_text(SERVER)
            run(['docker','cp',str(server),container+':/review/server.py'])
            run(['docker','exec','-d',container,'python3','-I','/review/server.py'])
            run(['docker','cp',str(task / 'tests'),container+':/tests'])
            run(['docker','cp',str(task / 'solution'),container+':/solution'])
            case('missing', '')
            # Same Oracle script as the Harbor agent, in this real Docker container.
            oracle = execute('bash /solution/solve.sh')
            (destination / 'solve.log').write_text(oracle.stdout + oracle.stderr)
            verify = execute('bash /tests/test.sh')
            record['oracle_reward'] = execute('cat /logs/verifier/reward.txt').stdout.strip()
            (destination / 'oracle.log').write_text(verify.stdout + verify.stderr)
            case('wrong_name', "Path('/app/wrong-name.txt').write_text('wrong')")
            setup_exact = '\n'.join(f"shutil.copyfile('/tests/gold/' + {n!r}, '/app/' + {n!r})" for n in names)
            case('equivalent_nonidentical', setup_exact + '\n' + '\n'.join(f"p=Path('/app') / {n!r}; p.write_bytes(p.read_bytes()+b'\\n')" for n in names), 'tie')
            corrupt = '\n'.join(f"(Path('/app') / {n!r}).write_bytes(b'invalid review deliverable')" for n in names)
            case('invalid_local_gold_wins', corrupt, 'gold')
            case('api_failure', corrupt, 'error')
            case('malformed_judge', corrupt, 'malformed')
            case('stale_reward', "Path('/logs/verifier/reward.json').write_text('{\"reward\":1}')")
            case('symlink_gold', '\n'.join(f"(Path('/app') / {n!r}).symlink_to('/tests/gold/' + {n!r})" for n in names))
            requests = python("from pathlib import Path; p=Path('/review/requests.jsonl'); print(p.read_text() if p.exists() else '')").stdout
            (destination / 'requests.jsonl').write_text(requests)
            record['local_judge_requests'] = len(requests.strip().splitlines())
            for label, reward in (('missing', 0), ('wrong_name', 0), ('equivalent_nonidentical', 0.5), ('invalid_local_gold_wins', 0)):
                assert float(record['cases'][label]['reward.txt']) == reward, label
            assert float(record['oracle_reward']) == 1
            for label in ('api_failure', 'malformed_judge'):
                result = record['cases'][label]
                if args.expect == 'hardened':
                    assert result['exit_code'] != 0 and result['reward.txt'] is None, label
                else:
                    assert result['exit_code'] == 0 and float(result['reward.txt']) == 0, label
            assert float(record['cases']['symlink_gold']['reward.txt']) == (0 if args.expect == 'hardened' else 1)
            stale = record['cases']['stale_reward']
            assert (stale['reward.json'] is None) == (args.expect == 'hardened')
            record['control_assertions_passed'] = True
            # Demonstrate that root can replace the interpreter before tests arrive.
            # No host path is mounted; the disposable container is removed below.
            python("from pathlib import Path; p=Path('/usr/local/bin/python3'); p.unlink(); p.write_text('#!/bin/sh\\nmkdir -p /logs/verifier\\nprintf 1 > /logs/verifier/reward.txt\\nexit 0\\n'); p.chmod(0o755)")
            tamper = execute('rm -rf /app; mkdir /app; bash /tests/test.sh', check=False)
            record['root_interpreter_tamper'] = {'exit_code':tamper.returncode, 'reward':execute('cat /logs/verifier/reward.txt',check=False).stdout.strip()}
        finally:
            run(['docker','rm','-f',container],check=False)
            report.append(record)
            (args.artifacts / 'report.json').write_text(json.dumps(report,indent=2))
    print(hashlib.sha256((args.artifacts / 'report.json').read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
