"""Canonical adapter CLI."""
import argparse
import json
from pathlib import Path
from .adapter import DeBenchUpgradeAdapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--task-ids', nargs='+')
    parser.add_argument('--split', choices=['full', 'smoke'], default='full')
    parser.add_argument('--environment-profile', choices=['scoring-smoke', 'upstream-runtime'], default='upstream-runtime',
                        help='Use scoring-smoke only for oracle/scorer tests, never agent parity')
    parser.add_argument('--package-index-url', default='https://pypi.org/simple/',
                        help='Index for full-runtime uv resolution; recorded in task provenance')
    parser.add_argument('--list-compatible', action='store_true')
    args = vars(parser.parse_args())
    inventory_only = args.pop('list_compatible')
    adapter = DeBenchUpgradeAdapter(**args)
    if inventory_only:
        print(json.dumps(adapter.inventory(), indent=2))
    else:
        print(json.dumps({'generated': adapter.run()}, indent=2))


if __name__ == '__main__':
    main()
