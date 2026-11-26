#!/usr/bin/env python3
"""Inspect a synthesized local CDK stack using the two read-only Fast commands."""

import argparse
import json
from pathlib import Path
import sys


def main() -> None:
    name = Path(sys.argv[0]).name
    cli = argparse.ArgumentParser(prog=name, description=__doc__)
    if name == "cdk_ls":
        cli.add_argument("--show-resources", action="store_true")
    else:
        cli.add_argument("--stack")
        cli.add_argument("--resource-type")
        cli.add_argument("--resource-pattern")
        cli.add_argument("--section")
    args = cli.parse_args()
    from core_infrastructure.app import app

    stacks = app.synth().stacks
    if name == "cdk_ls":
        for stack in stacks:
            print(stack.stack_name)
            if args.show_resources:
                for key, resource in stack.template.get("Resources", {}).items():
                    print(f"  {key}: {resource['Type']}")
        return
    selected = [stack for stack in stacks if args.stack is None or stack.stack_name == args.stack]
    if not selected:
        cli.error("No stack with that name")
    for stack in selected:
        template = stack.template
        if args.resource_type or args.resource_pattern:
            template = {"Resources": {
                key: value for key, value in template.get("Resources", {}).items()
                if (not args.resource_type or value["Type"] == args.resource_type)
                and (not args.resource_pattern or args.resource_pattern.lower() in key.lower())
            }}
        if args.section:
            if args.section not in template:
                cli.error("Template has no matching section")
            template = template[args.section]
        print(json.dumps(template, indent=2))


if __name__ == "__main__":
    main()
