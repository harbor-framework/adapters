"""Offline integration test: mocked HTTP responses through real Harbor Docker trials.

This checks one correct and one incorrect answer, plus resume deduplication.
It is NOT model parity evidence and makes zero network/model API calls.
"""

import argparse
import asyncio
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from supergpqa import direct
from supergpqa.parity import harbor_one, original_one, prepare


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.upstream_repo.resolve(), args.output_dir.resolve()
    rows, prompts, upstream_parser = prepare(root, output)
    answers = {
        prompts[rows[0]["uuid"]]: f"Answer: {rows[0]['answer_letter']}",
        prompts[rows[1]["uuid"]]: "Answer: Z",
    }
    calls = []

    class MockOpener:
        def open(self, request, timeout):
            payload = json.loads(request.data)
            instruction = payload["messages"][0]["content"]
            calls.append(direct.digest(payload))
            return io.BytesIO(
                json.dumps(
                    {
                        "model": "OFFLINE-MOCK-NOT-A-MODEL",
                        "usage": {},
                        "choices": [
                            {
                                "message": {"content": answers[instruction]},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                ).encode()
            )

    with (
        patch.object(direct, "build_opener", lambda *_: MockOpener()),
        patch.object(direct, "EXPECTED_RETURNED_MODEL", "OFFLINE-MOCK-NOT-A-MODEL"),
    ):
        os.environ["SUPERGPQA_API_KEY"] = "offline-test-only-not-a-real-key"
        os.environ["SUPERGPQA_BASE_URL"] = "https://offline.invalid/v1"
        results = []
        for row in rows[:2]:
            prompt = prompts[row["uuid"]]
            original = await original_one(
                row, prompt, upstream_parser, output / "original" / row["uuid"]
            )
            harbor = await harbor_one(
                row,
                prompt,
                upstream_parser,
                output / "harbor" / row["uuid"],
                output / "tasks",
            )
            if original != harbor:
                raise AssertionError("Original/Harbor offline control mismatch")
            results.append(original)
        if [r["reward"] for r in results] != [1, 0] or len(calls) != 4:
            raise AssertionError("Offline controls or call counts differ")
        for row in rows[:2]:
            await original_one(
                row,
                prompts[row["uuid"]],
                upstream_parser,
                output / "original" / row["uuid"],
            )
            await harbor_one(
                row,
                prompts[row["uuid"]],
                upstream_parser,
                output / "harbor" / row["uuid"],
                output / "tasks",
            )
        if len(calls) != 4:
            raise AssertionError("Resume repeated an API call")
        direct.save_json(
            output / "offline-docker-validation.json",
            {
                "kind": "offline_mock_transport_real_harbor_docker",
                "model_calls": 0,
                "mock_http_calls": len(calls),
                "resume_extra_calls": 0,
                "scores": results,
                "both_sides_agree": True,
                "is_model_parity_evidence": False,
            },
        )
        print(
            "Offline Docker harness passed: correct=1, incorrect=0, resume extra calls=0. NOT model parity."
        )


if __name__ == "__main__":
    asyncio.run(main())
