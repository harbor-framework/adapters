"""ResearchRubrics verifier: grade /app/report.md against the task's expert rubrics.

Port of the upstream evaluator (scaleapi/researchrubrics @ 2dc80e2,
src/evaluate_rubrics/evaluate_single_report.py and
src/calculate_metrics/calculate_compliance_score.py). The prompts in
prompts/ are copied verbatim. Behaviour kept identical to upstream:

- binary grading (Satisfied = 1.0, Not Satisfied = 0.0), one judge call per rubric
- system + user prompt, JSON response format, max_tokens = 50000
- up to 3 attempts per rubric; a rubric that still fails scores 0.0
- documents over (200000 - 50000) estimated tokens are chunked (100000 tokens
  per chunk) and graded via the chunk + synthesis prompts
- compliance = sum(weight * score) / sum(positive weights); negative-weight
  rubrics only subtract, so the score can drop below 0

The judge model and endpoint are configurable through environment variables
(see task.toml [verifier.env]); upstream used Gemini 2.5 Pro through LiteLLM.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import litellm

litellm.suppress_debug_info = True

REPORT_FILE = Path("/app/report.md")
TESTS_DIR = Path(__file__).parent
RUBRICS_FILE = TESTS_DIR / "rubrics.json"
PROMPTS_DIR = TESTS_DIR / "prompts"
VERIFIER_DIR = Path("/logs/verifier")

JUDGE_MODEL = os.environ.get("JUDGE_MODEL") or "gemini/gemini-2.5-pro"
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY") or None
JUDGE_API_BASE = os.environ.get("JUDGE_API_BASE") or None
# Only needed for Azure-style gateways (JUDGE_MODEL="azure/<deployment>").
JUDGE_API_VERSION = os.environ.get("JUDGE_API_VERSION") or None
JUDGE_MAX_TOKENS = int(os.environ.get("JUDGE_MAX_TOKENS") or 50000)
JUDGE_MAX_CONCURRENT = int(os.environ.get("JUDGE_MAX_CONCURRENT") or 20)
ORACLE_MODE = (os.environ.get("ORACLE_MODE") or "").lower() == "true"

# Upstream hardcodes Gemini 2.5 Pro's context window and reserves 50k tokens.
CONTEXT_LIMIT_TOKENS = 200000 - 50000
CHUNK_MAX_TOKENS = 100000

SYSTEM_PROMPT = (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")
USER_PROMPT_TEMPLATE = (PROMPTS_DIR / "user_prompt.txt").read_text(encoding="utf-8")
CHUNK_PROMPT_TEMPLATE = (PROMPTS_DIR / "chunk_prompt_template.txt").read_text(
    encoding="utf-8"
)
SYNTHESIS_PROMPT_TEMPLATE = (PROMPTS_DIR / "synthesis_prompt_template.txt").read_text(
    encoding="utf-8"
)


async def _complete(system: str, user: str):
    return await litellm.acompletion(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=JUDGE_MAX_TOKENS,
        response_format={"type": "json_object"},
        api_key=JUDGE_API_KEY,
        base_url=JUDGE_API_BASE,
        api_version=JUDGE_API_VERSION,
        # LiteLLM silently drops response_format for Azure deployments it does
        # not recognize (e.g. Gemini behind an Azure-style gateway); keep it so
        # the judge returns bare JSON exactly as upstream expects.
        allowed_openai_params=["response_format"],
    )


def chunk_document(content: str, max_tokens: int = CHUNK_MAX_TOKENS) -> list[str]:
    max_chars = max_tokens * 4
    if len(content) <= max_chars:
        return [content]

    chunks = []
    current_chunk = ""
    for para in content.split("\n\n"):
        if len(current_chunk) + len(para) < max_chars:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


async def _evaluate_single(rubric: dict, content: str) -> dict:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        document_content=content,
        rubric_title=rubric["criterion"],
        rubric_category=rubric["axis"],
        rubric_weight=rubric["weight"],
    )
    for attempt in range(3):
        try:
            response = await _complete(SYSTEM_PROMPT, user_prompt)
            data = json.loads(response.choices[0].message.content)
            return {
                "verdict": data.get("verdict"),
                "score": float(data.get("score")),
                "confidence": float(data.get("confidence")),
                "reasoning": data.get("reasoning"),
                "judge_model_served": response.model,
            }
        except json.JSONDecodeError as e:
            print(f"JSON decode error on attempt {attempt + 1}: {e}", file=sys.stderr)
            if attempt == 2:
                raise
        except Exception as e:
            print(f"Judge call failed on attempt {attempt + 1}: {e}", file=sys.stderr)
            if attempt == 2:
                raise
            await asyncio.sleep(2**attempt)


async def _evaluate_with_chunks(rubric: dict, content: str) -> dict:
    chunks = chunk_document(content)
    all_evidence = []
    for i, chunk in enumerate(chunks, 1):
        chunk_prompt = CHUNK_PROMPT_TEMPLATE.format(
            chunk_num=i,
            total_chunks=len(chunks),
            context_summary="Previous chunks evaluated" if i > 1 else "First chunk",
            chunk_content=chunk,
            rubric_title=rubric["criterion"],
            rubric_category=rubric["axis"],
        )
        response = await _complete(
            "You are evaluating document chunks for rubric criteria.", chunk_prompt
        )
        chunk_data = json.loads(response.choices[0].message.content)
        all_evidence.extend(chunk_data["relevant_evidence"])

    synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        all_evidence=json.dumps(all_evidence, indent=2),
        rubric_title=rubric["criterion"],
        rubric_category=rubric["axis"],
    )
    response = await _complete(SYSTEM_PROMPT, synthesis_prompt)
    data = json.loads(response.choices[0].message.content)
    return {
        "verdict": data.get("verdict", "Unknown"),
        "score": float(data.get("score")),
        "confidence": float(data.get("confidence")),
        "reasoning": data.get("reasoning"),
        "judge_model_served": response.model,
    }


async def evaluate_rubric(
    rubric: dict, content: str, semaphore: asyncio.Semaphore
) -> dict:
    async with semaphore:
        try:
            if len(content) // 4 > CONTEXT_LIMIT_TOKENS:
                result = await _evaluate_with_chunks(rubric, content)
            else:
                result = await _evaluate_single(rubric, content)
            result["success"] = True
        except Exception as e:
            print(f"Evaluation failed: {e}", file=sys.stderr)
            result = {
                "verdict": "Error",
                "score": 0.0,
                "confidence": 0.0,
                "reasoning": f"Evaluation failed: {e}",
                "judge_model_served": None,
                "success": False,
            }
    return {**rubric, **result}


def compliance_score(results: list[dict]) -> float:
    numerator = sum(r["score"] * r["weight"] for r in results)
    denominator = sum(r["weight"] for r in results if r["weight"] > 0)
    return numerator / denominator if denominator > 0 else 0.0


async def main() -> int:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    rubrics = json.loads(RUBRICS_FILE.read_text())

    content = REPORT_FILE.read_text(encoding="utf-8") if REPORT_FILE.exists() else ""
    if not content:
        # Upstream skips reports it cannot load, so they contribute 0.
        print(f"No report found at {REPORT_FILE} (or it is empty); reward = 0")
        (VERIFIER_DIR / "reward.txt").write_text("0.0")
        return 0

    if ORACLE_MODE:
        # Pipeline check only (same approach as the clbench adapter): the report
        # was written and the rubrics load. No judge calls, so this says nothing
        # about grading correctness.
        if not rubrics or not all(
            {"criterion", "weight", "axis"} <= rubric.keys() for rubric in rubrics
        ):
            print("ORACLE_MODE: rubrics.json is empty or malformed", file=sys.stderr)
            return 1
        print(f"ORACLE_MODE: report present ({len(content)} chars), {len(rubrics)} rubrics loaded; reward = 1")
        (VERIFIER_DIR / "reward.txt").write_text("1.0")
        return 0

    print(f"Judge: {JUDGE_MODEL}; report: {len(content)} chars; rubrics: {len(rubrics)}")
    semaphore = asyncio.Semaphore(JUDGE_MAX_CONCURRENT)
    results = await asyncio.gather(
        *[evaluate_rubric(rubric, content, semaphore) for rubric in rubrics]
    )

    with open(VERIFIER_DIR / "rubric_results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    n_failed = sum(not r["success"] for r in results)
    if n_failed == len(results):
        # Every judge call failed: almost certainly a judge configuration problem
        # (missing key, bad model name). Fail the verifier instead of reporting 0.
        print("All judge calls failed; not writing a reward.", file=sys.stderr)
        return 1

    score = compliance_score(results)
    summary = {
        "compliance_score": score,
        "judge_model": JUDGE_MODEL,
        # Model names the endpoint reported back; a gateway may route the
        # requested name to a different model.
        "judge_models_served": sorted(
            {r["judge_model_served"] for r in results if r["judge_model_served"]}
        ),
        "n_rubrics": len(results),
        "n_satisfied": sum(r["score"] >= 1.0 for r in results),
        "n_judge_errors": n_failed,
    }
    (VERIFIER_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    (VERIFIER_DIR / "reward.txt").write_text(str(score))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
