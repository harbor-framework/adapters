"""Compatibility entry point: case 040 public-tool construction, no grader."""
import argparse
from pathlib import Path
from reference_tools import PublicTools
from reference_plans import case_040
from bizagentbench.source import validate_source

parser=argparse.ArgumentParser()
parser.add_argument('--source-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
validate_source(args.source_dir)
if args.output.exists():
    raise FileExistsError('Preserve prior attempts; choose a new output directory')
client=PublicTools(args.source_dir.resolve(),'case_040',args.output.resolve())
try:
    case_040(client)
    assert client.finished
finally:
    client.close()
print('Constructed case_040; grade only in a subsequent isolated container')
