"""Run baseline/oracle/targeted regression states in a fresh Docker container.

Use a scoring-smoke generated dataset. Requires a locally built scoring image;
never runs an agent or calls a model API. Each result includes original scoring
checks. Partial reversion is recorded even when remaining edits still pass.
"""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=Path, required=True)
parser.add_argument('--image', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
selection = json.loads((args.dataset / 'selection.json').read_text())
rows = []
for task_id in selection['task_ids']:
    task = (args.dataset / task_id).resolve()
    for state in ('baseline', 'oracle', 'partial_reversion'):
        command = '''set -eu
rm -rf /work
mkdir -p /work /logs/verifier
cp -a /case/environment/workspace/. /work/
if [ "$1" = oracle ] || [ "$1" = partial_reversion ]; then
  python /case/solution/apply.py /case/solution/overlay /work
else
  echo reviewed > /work/NOTES.txt
fi
if [ "$1" = partial_reversion ]; then
  # Restore original requirements where present; otherwise restore the DAG tree.
  if [ -f /case/environment/workspace/requirements.txt ]; then
    cp /case/environment/workspace/requirements.txt /work/requirements.txt
  else
    rm -rf /work/dags
    cp -a /case/environment/workspace/dags /work/dags
  fi
  echo reviewed > /work/NOTES.txt
fi
python -I /tests/verify.py --workspace /work --output-dir /logs/verifier >/tmp/scoring.log
cat /logs/verifier/result.json
'''
        proc = subprocess.run(['docker','run','--rm','--network','none',
              '-v',f'{task}:/case:ro','-v',f'{task / "tests"}:/tests:ro',
              args.image,'bash','-c',command,'state',state],capture_output=True,text=True)
        if proc.returncode: raise RuntimeError(proc.stderr)
        result = json.loads(proc.stdout)
        rows.append(dict(task_id=task_id,state=state,**result))
        if state != 'partial_reversion':
            assert result['pass'] == (state=='oracle'), rows[-1]
        # A targeted reversion need not break every task (some requirements are
        # unchanged or ungraded). Record the result, never invent a failing check.
        print(task_id,state,result['pass'],flush=True)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(dict(image=args.image, upstream_commit=selection['upstream_commit'], rows=rows),indent=2)+'\n')
