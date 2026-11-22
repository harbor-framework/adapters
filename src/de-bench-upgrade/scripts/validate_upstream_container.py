"""Execute upstream's original score-trial body locally in Docker, without Modal.

Only static upgrade-v2 tasks at the audited revision are admitted. AST extraction
loads exact function bodies, not rewritten scoring logic or a mock Modal client.
This validates the original rebuild/apply/score orchestration but not Modal's
image, platform, or agent execution.
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

PIN = '5dcfc2b81b13dcf58cff49e192e97f1ae05f8dbc'


def inside():
    sys.path.insert(0, '/upstream/src')
    from de_bench.tasks import load_tasks, workspace_tar, oracle_tar
    root = Path('/upstream')
    namespace = dict(subprocess=subprocess, shutil=shutil, Path=Path, workspace_tar=workspace_tar)
    def load_functions(path, names):
        tree = ast.parse(path.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        if len(nodes) != len(names): raise ValueError('Upstream function set changed')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    load_functions(root / 'src/de_bench/cli.py', {'_solution_patch'})
    load_functions(root / 'src/de_bench/modal_app.py',
                   {'_score_trial','_prepare_workspace_extras','_pin_warehouse_clock'})
    baseline = ('diff --git a/NOTES.txt b/NOTES.txt\nnew file mode 100644\nindex 0000000..bd42003\n'
                '--- /dev/null\n+++ b/NOTES.txt\n@@ -0,0 +1 @@\n+reviewed\n').encode()
    rows = []
    for task in load_tasks(root):
        if task.world.name != 'upgrade-v2': continue
        if task.live_env or task.history or task.verifier_dir or task.env or task.setup_sql or task.workspace_data or task.world.generated:
            raise ValueError('Unsupported runtime features')
        if any(c['kind'] != 'scoring_primitive' for c in task.checks):
            raise ValueError('Unsupported runtime check')
        for state, patch in [('baseline',baseline),('oracle',namespace['_solution_patch'](task))]:
            spec = dict(config=state,task_id=task.id,trial=0,patch=patch,
                        workspace_tar=workspace_tar(task),oracle_tar=oracle_tar(task),
                        checks=list(task.checks),do_not_modify=list(task.do_not_modify),
                        replay_dags=list(task.replay_dags or ()),live_env=False)
            with contextlib.redirect_stdout(io.StringIO()):
                result = namespace['_score_trial'](spec)
            assert result.get('score_outcome') == 'scored', result
            assert result['pass'] == (state=='oracle'), result
            rows.append(result)
    print(json.dumps(dict(upstream_commit=PIN,kind='original-score-trial-body-in-local-docker',rows=rows)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside',action='store_true')
    parser.add_argument('--upstream-root',type=Path)
    parser.add_argument('--image')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.inside:
        inside();return
    revision=subprocess.check_output(['git','-C',str(args.upstream_root),'rev-parse','HEAD'],text=True).strip()
    if revision != PIN: raise ValueError('Wrong upstream revision')
    command=['docker','run','--rm','--network','none',
             '-v',f'{args.upstream_root.resolve()}:/upstream:ro',
             '-v',f'{Path(__file__).resolve()}:/runner.py:ro',
             args.image,'python','-I','/runner.py','--inside']
    result=subprocess.run(command,capture_output=True,text=True,check=True)
    data=json.loads(result.stdout)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print(f"Original scorer: {len(data['rows'])} baseline/oracle states validated")


if __name__=='__main__': main()
