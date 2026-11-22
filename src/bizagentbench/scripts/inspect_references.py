"""Read-only discovery of public business records, without grading."""
import argparse
import re
from pathlib import Path
from reference_tools import PublicTools
from bizagentbench.source import validate_source

parser = argparse.ArgumentParser()
parser.add_argument('--source-dir', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--task-ids', nargs='+', required=True)
args = parser.parse_args()
validate_source(args.source_dir)
for task_id in args.task_ids:
    target = args.output / task_id
    if target.exists():
        raise FileExistsError(target)
    p = PublicTools(args.source_dir.resolve(), task_id, target.resolve())
    try:
        p.call('assistant', 'read_document', document_id='PAYMENT-CATALOG')
        try:
            cases = p.rows('xp_cases')
        except RuntimeError as error:
            if 'PRODUCT_NOT_ENABLED' not in str(error):
                raise
            cases = None
        if cases is not None:
            p.docs()
            for case in cases:
                for resource in case['related_resources']:
                    p.rows(resource)
                p.call('assistant', 'search_knowledge', query=case['name'])
            p.rows('xp_accounts')
        else:
            guide = p.call('assistant', 'read_document', document_id='DB-index')
            resources = re.findall(r'^\| ([a-z_]+) \|', guide['content'], re.M)
            for resource in resources:
                if resource != 'events':
                    p.rows(resource)
        p.call('user', 'list_my_files')
        print(task_id, 'public inspection complete', flush=True)
    finally:
        p.close()
