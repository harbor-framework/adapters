#!/usr/bin/env python3
"""Query the local AgentDojo travel directory using its read-only lookup functions."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from native_lookups import TOOLS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lookup", choices=sorted(TOOLS))
    parser.add_argument("values", nargs="+", help="City for a city listing, otherwise one or more business names")
    args = parser.parse_args()
    fixture = json.loads(Path(__file__).resolve().with_name("inventory.json").read_bytes(), object_hook=lambda fields: SimpleNamespace(**fields))
    if args.lookup in {"get_all_restaurants_in_city", "get_all_car_rental_companies_in_city"}:
        if len(args.values) != 1:
            parser.error("The city listing expects exactly one city")
        result = TOOLS[args.lookup](fixture, args.values[0])
    else:
        result = TOOLS[args.lookup](fixture, args.values)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
