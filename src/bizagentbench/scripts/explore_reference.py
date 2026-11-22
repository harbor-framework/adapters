"""Public-tool developer console; scoring is a separate, post-run operation.

Each stdin line is exactly {actor, tool, arguments}. No verify or state RPC exists.
The trusted subprocess saves artifacts after closure for isolated diagnostics.
"""
import argparse
import json
from pathlib import Path
from reference_tools import PublicTools
from bizagentbench.source import validate_source

parser=argparse.ArgumentParser()
parser.add_argument('--source-dir',type=Path,required=True)
parser.add_argument('--task-id',required=True)
parser.add_argument('--trace',type=Path,required=True)
args=parser.parse_args()
validate_source(args.source_dir)
output=args.trace.parent/(args.trace.stem+'-construction')
if args.trace.exists() or output.exists():
    raise FileExistsError('Preserve prior attempts; choose a new trace path')
client=PublicTools(args.source_dir.resolve(),args.task_id,output.resolve())
args.trace.parent.mkdir(parents=True,exist_ok=True)
try:
    import sys
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if set(request)!={'actor','tool','arguments'}:
                raise ValueError('Only role-scoped public tool requests are accepted; grading is isolated')
            result=client.call(request['actor'],request['tool'],**request['arguments'])
            row={'request':request,'response':result}
            with args.trace.open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(result,ensure_ascii=False),flush=True)
        except Exception as exc:
            print(json.dumps({'console_error':type(exc).__name__,'detail':str(exc)}),flush=True)
finally:
    client.close()
