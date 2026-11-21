"""Isolate Inspect's event loop and display state from Harbor's orchestrator."""

import asyncio
import json
import os
import sys
from pathlib import Path

from .runtime import run_upstream
from .outcomes import IncompleteEvaluation, usage_summary


async def main():
    request = json.loads(sys.stdin.read())
    key_name = request.pop("api_key_name", None)
    destination = Path(request.pop("result_path"))
    try:
        answer, log = await run_upstream(
            **request, api_key=os.environ.get(key_name) if key_name else None
        )
    except IncompleteEvaluation as error:
        destination.with_name("failure.json").write_text(json.dumps(error.result, indent=2) + "\n")
        raise
    usage = usage_summary(log.stats.model_usage if log.stats else None)
    result = {
        "answer": answer,
        "inspect_log": log.location,
        "sample_metadata": log.samples[0].metadata,
        "usage": usage,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
    }
    destination.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
