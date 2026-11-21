from __future__ import annotations

import argparse
from pathlib import Path

from .adapter import SCENARIOS, SUPPORTED_LANGUAGES, SeccodebenchAdapter

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "datasets" / "seccodebench"

# Parity subset (16 of 328 tasks, ~5%): one task per case, 16 distinct cases split by
# language in proportion to case counts (cpp 3, go 2, java 8, nodejs 1, python 2), drawn
# once with random.Random(20261120).sample over the sorted case ids of each language,
# excluding REQUIRES_NETWORK_AT_VERIFY cases (flaky live-site tests); scenarios
# alternate gen/fix in that order.
PARITY_TASK_IDS = [
    "cpp-bufferoverflowvla-gen",
    "cpp-doublefreeconditional-fix",
    "cpp-doublefreedirect-gen",
    "go-oauthconstantstatevalue-fix",
    "go-sqlinjectionstd-gen",
    "java-commandinjectionruntime-fix",
    "java-deserializationflexjson-gen",
    "java-deserializationxmldecoder-fix",
    "java-jdbcinjection-gen",
    "java-pathtraversalwrite-fix",
    "java-xxejdom2-gen",
    "java-xxexmlreader-fix",
    "java-zipslip-gen",
    "nodejs-commandinjectionshell-fix",
    "python-deserializationtorchload-gen",
    "python-sqlinjectionpymysql-fix",
]


def main() -> None:
    p = argparse.ArgumentParser(description="Generate Harbor tasks for SecCodeBench")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--limit", type=int, default=None, help="Generate only the first N tasks")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing task dirs")
    p.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Task ids (e.g. python-ssrfurllib-gen) or upstream case ids (e.g. SSRFUrllib)",
    )
    p.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Existing alibaba/sec-code-bench checkout (cloned at the pinned commit if omitted)",
    )
    p.add_argument("--languages", nargs="+", choices=SUPPORTED_LANGUAGES, default=None)
    p.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=None)
    p.add_argument(
        "--solution-mode",
        choices=("oracle", "vulnerable"),
        default="oracle",
        help="'vulnerable' ships the upstream vulnerable template as solution (negative control)",
    )
    p.add_argument(
        "--include-llm-judge",
        action="store_true",
        help="Also generate cases graded by an upstream LLM judge (excluded by default)",
    )
    p.add_argument(
        "--include-broken",
        action="store_true",
        help="Also generate cases in BROKEN_CASES (upstream tests verifiably broken)",
    )
    p.add_argument(
        "--exclude-network-tests",
        action="store_true",
        help="Skip cases in REQUIRES_NETWORK_AT_VERIFY (verifier needs live third-party sites)",
    )
    p.add_argument(
        "--split",
        choices=("full", "parity"),
        default="full",
        help="'parity' generates only the parity subset (PARITY_TASK_IDS)",
    )
    args = p.parse_args()
    if args.split == "parity":
        if args.task_ids or args.languages or args.scenarios:
            p.error("--split parity cannot be combined with --task-ids/--languages/--scenarios")
        args.task_ids = PARITY_TASK_IDS
    if args.limit is not None and args.limit < 1:
        p.error("--limit must be >= 1")

    written = SeccodebenchAdapter(
        output_dir=args.output_dir,
        source_dir=args.source_dir,
        limit=args.limit,
        overwrite=args.overwrite,
        task_ids=args.task_ids,
        languages=args.languages,
        scenarios=args.scenarios,
        solution_mode=args.solution_mode,
        include_llm_judge=args.include_llm_judge,
        include_broken=args.include_broken,
        exclude_network_tests=args.exclude_network_tests,
    ).run()
    print(f"Wrote {len(written)} tasks to {args.output_dir}")


if __name__ == "__main__":
    main()
