"""Invoke the pinned example unchanged; also usable on the original benchmark side."""

import argparse
import json
import os
import random
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--upstream", type=Path, default=Path("/opt/flashinfer-bench"))
    p.add_argument("--data", type=Path, default=Path("/workspace/data"))
    p.add_argument("--manifest", type=Path, default=Path("/workspace/manifest.json"))
    p.add_argument("--output", type=Path, default=Path("/workspace/solution.json"))
    p.add_argument("--model", required=True)
    p.add_argument("--language", choices=["triton", "cuda"], default="triton")
    p.add_argument("--rounds", type=int, default=10)
    p.add_argument("--attempts", type=int, default=2)
    p.add_argument("--reasoning-effort", default="high")
    p.add_argument("--seed", type=int)
    args = p.parse_args()
    if args.rounds < 1 or args.attempts < 1:
        p.error("rounds and attempts must be positive")
    args.output.unlink(missing_ok=True)
    sys.path.insert(0, str(args.upstream / "examples/kernel_generator"))
    from assets import check_gpu, prepare
    from kernel_generator import KernelGenerator

    from flashinfer_bench import TraceSet

    manifest = json.loads(args.manifest.read_text())
    check_gpu(manifest["target_gpu"])
    prepare(args.data, manifest, Path("/tmp/flashinfer-tensors"))
    traces = TraceSet.from_path(str(args.data))
    if args.seed is not None:
        random.seed(args.seed)
    generator = KernelGenerator(
        model_name=args.model,
        language=args.language,
        target_gpu=manifest["target_gpu"],
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ.get("BASE_URL"),
        reasoning_effort=args.reasoning_effort,
        use_ffi=False,
    )
    for attempt in range(args.attempts):
        try:
            solution = generator.generate(
                traces,
                traces.definitions[manifest["definition"]],
                gen_rounds=args.rounds,
            )
        except Exception:
            if attempt + 1 == args.attempts:
                raise
            print(f"Retrying generation ({attempt + 2}/{args.attempts})", flush=True)
        else:
            # The example driver saves after generation, outside its retry loop.
            # A serialization/disk error must not spend another model attempt.
            args.output.write_text(solution.model_dump_json(indent=2) + "\n")
            return


if __name__ == "__main__":
    main()
