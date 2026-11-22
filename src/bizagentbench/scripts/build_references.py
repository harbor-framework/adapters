"""Construct references using public tool responses; never run a grader here."""
import argparse
import json
from pathlib import Path
from reference_tools import PublicTools
import reference_plans
from bizagentbench.source import validate_source

parser = argparse.ArgumentParser()
parser.add_argument('--source-dir', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--task-ids', nargs='+', required=True)
args = parser.parse_args()
validate_source(args.source_dir)
failed = []
for task_id in args.task_ids:
    target = args.output / task_id
    if target.exists():
        raise FileExistsError(f'Keep prior attempts: choose a new output path: {target}')
    client = PublicTools(args.source_dir.resolve(), task_id, target.resolve())
    try:
        getattr(reference_plans, task_id)(client)
        assert client.finished, 'Inspection only: reference has no terminal outcome'
        print(task_id, 'constructed; not yet graded', flush=True)
    except Exception as error:
        failed.append(task_id)
        target.mkdir(parents=True, exist_ok=True)
        (target / 'construction-error.json').write_text(json.dumps({'error': repr(error)}, indent=2), 'utf-8')
        print(task_id, repr(error), flush=True)
    finally:
        client.close()
raise SystemExit(bool(failed))
