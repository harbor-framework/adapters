"""Offline comparison against the pinned upstream scorer; no Modal or model API.

Loads the exact upstream _solution_patch function using AST, avoiding unrelated
CLI/Modal imports. Baseline follows de-bench prove (NOTES.txt marks delivery).
This is scoring equivalence evidence, not agent or Modal parity.
"""
import argparse
import ast
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--upstream-root', type=Path, required=True)
parser.add_argument('--dataset', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.upstream_root / 'src'))
from de_bench.tasks import load_tasks, workspace_tar
from de_bench.scoring import score_workspace

source = ast.parse((args.upstream_root / 'src/de_bench/cli.py').read_text())
node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == '_solution_patch')
namespace = dict(subprocess=subprocess, shutil=shutil, Path=Path, workspace_tar=workspace_tar)
exec(compile(ast.Module(body=[node], type_ignores=[]), 'upstream/_solution_patch', 'exec'), namespace)
solution_patch = namespace['_solution_patch']
selection = json.loads((args.dataset / 'selection.json').read_text())
tasks = {t.id:t for t in load_tasks(args.upstream_root)}
rows = []
log = io.StringIO()
for task_id in selection['task_ids']:
    task = tasks[task_id]
    generated = args.dataset / task_id
    for state in ('untouched', 'baseline', 'oracle', 'broken'):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(log):
            root = Path(temporary)
            work = root / 'work'
            work.mkdir()
            with tarfile.open(fileobj=io.BytesIO(workspace_tar(task)), mode='r:gz') as tar:
                tar.extractall(work, filter='data')
            def git(*command):
                return subprocess.check_output(['git','-C',str(work),*command], stderr=subprocess.PIPE)
            git('init','-q'); git('add','-A')
            git('-c','user.name=bench','-c','user.email=bench@localhost','commit','-qm','baseline')
            if state in ('oracle','broken'):
                patchfile = root / 'oracle.patch'
                patchfile.write_bytes(solution_patch(task))
                git('apply','--binary',str(patchfile))
            if state == 'baseline': (work / 'NOTES.txt').write_text('reviewed\n')
            if state == 'broken':
                # Revert solution files while retaining a delivered marker; all
                # migration assertions must run, rather than fail only delivered.
                git('reset','--hard','HEAD'); git('clean','-fd')
                (work / 'NOTES.txt').write_text('reviewed\n')
            git('add','-A')
            patch = git('diff','--cached','--binary','HEAD').decode(errors='replace')
            original = score_workspace(str(work), list(task.checks), list(task.do_not_modify), patch,
                         baseline_dags=[], replay_dags=list(task.replay_dags or ()), oracle_dir=str(task.dir))
            # Commit the output to ensure verifier does not use agent HEAD as baseline.
            if patch: git('-c','user.name=bench','-c','user.email=bench@localhost','commit','-qm','agent committed fix')
            proc = subprocess.run([sys.executable,'-I',str(generated / 'tests/verify.py'),
                     '--workspace',str(work),'--output-dir',str(root / 'result')], capture_output=True, text=True)
            if proc.returncode: raise RuntimeError(proc.stderr)
            adapted = json.loads((root / 'result/result.json').read_text())
            checks = lambda result: {k:v['passed'] for k,v in result['checks'].items()}
            equal = original['pass'] == adapted['pass'] and checks(original) == checks(adapted)
            row = dict(task_id=task_id, state=state, original_pass=original['pass'],
                       harbor_wrapper_pass=adapted['pass'], checks_match=equal,
                       original_checks=checks(original), harbor_checks=checks(adapted))
            rows.append(row)
            assert equal, row
            assert original['pass'] == (state == 'oracle'), row
    print(task_id, 'four states matched')
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(dict(upstream_commit=selection['upstream_commit'],
       kind='local-scoring-comparison-not-agent-parity', comparisons=len(rows), rows=rows), indent=2)+'\n')
args.output.with_suffix('.log').write_text(log.getvalue())
