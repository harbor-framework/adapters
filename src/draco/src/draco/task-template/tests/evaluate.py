"""DRACO verifier: grade /app/report.md against the task's expert rubric.

Uses the grader library the paper links to (paper-instruments/rubric, formerly
The-LLM-Data-Company/rubric, @ eb0755a). Its PerCriterionGrader supplies the
judge prompt (the library default, which matches the paper's Appendix C.5) and
the scoring; this script only supplies the LLM call, which the library leaves
to the caller:

- one judge call per criterion with the query, the report and the criterion
  type (positive / negative weight); binary MET / UNMET verdicts
- score = clamp(sum(w_i * met_i) / sum(positive w_i), 0, 1)

The judge is called through LiteLLM. Defaults follow the paper's primary judge
(Table 16): Gemini-3-Pro with thinking level low and temperature 0.2. Model,
endpoint and sampling settings are configurable through environment variables
(see task.toml [verifier.env]).
"""

import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path

import litellm
from rubric import Criterion, PerCriterionOutput
from rubric.autograders import PerCriterionGrader

litellm.suppress_debug_info = True

REPORT_FILE = Path("/app/report.md")
TASK_FILE = Path(__file__).parent / "task.json"
VERIFIER_DIR = Path("/logs/verifier")

JUDGE_MODEL = os.environ.get("JUDGE_MODEL") or "gemini/gemini-3-pro-preview"
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY") or None
JUDGE_API_BASE = os.environ.get("JUDGE_API_BASE") or None
# Only needed for Azure-style gateways (JUDGE_MODEL="azure/<deployment>").
JUDGE_API_VERSION = os.environ.get("JUDGE_API_VERSION") or None
# Empty means "do not send", so the provider default applies.
JUDGE_TEMPERATURE = os.environ.get("JUDGE_TEMPERATURE", "0.2")
JUDGE_REASONING_EFFORT = os.environ.get("JUDGE_REASONING_EFFORT", "low")
JUDGE_MAX_ATTEMPTS = int(os.environ.get("JUDGE_MAX_ATTEMPTS") or 5)
JUDGE_MAX_CONCURRENT = int(os.environ.get("JUDGE_MAX_CONCURRENT") or 20)
ORACLE_MODE = (os.environ.get("ORACLE_MODE") or "").lower() == "true"

_semaphore = asyncio.Semaphore(JUDGE_MAX_CONCURRENT)
# Model names the endpoint reported back; a gateway may route the requested
# name to a different model.
_models_served: set[str] = set()


def _parse_output(content: str) -> PerCriterionOutput:
    try:
        return PerCriterionOutput.model_validate_json(content)
    except ValueError:
        # Some gateways ignore the response schema and wrap the JSON in prose or
        # a Markdown fence; the library leaves parsing to the caller.
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match is None:
            raise
        return PerCriterionOutput.model_validate_json(match.group(0))


async def generate(system_prompt: str, user_prompt: str, **kwargs) -> PerCriterionOutput:
    """PerCriterionGenerateFn for the library: one judge call, with retries."""
    params = {}
    allowed = ["response_format"]
    if JUDGE_TEMPERATURE:
        params["temperature"] = float(JUDGE_TEMPERATURE)
    if JUDGE_REASONING_EFFORT:
        params["reasoning_effort"] = JUDGE_REASONING_EFFORT
        allowed.append("reasoning_effort")

    async with _semaphore:
        for attempt in range(JUDGE_MAX_ATTEMPTS):
            try:
                response = await litellm.acompletion(
                    model=JUDGE_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=PerCriterionOutput,
                    api_key=JUDGE_API_KEY,
                    base_url=JUDGE_API_BASE,
                    api_version=JUDGE_API_VERSION,
                    # LiteLLM silently drops these for Azure deployments it does
                    # not recognize (e.g. Gemini behind an Azure-style gateway).
                    allowed_openai_params=allowed,
                    **params,
                )
                output = _parse_output(response.choices[0].message.content or "")
                _models_served.add(response.model)
                return output
            except Exception as e:
                print(f"Judge call failed on attempt {attempt + 1}: {e}", file=sys.stderr)
                if attempt == JUDGE_MAX_ATTEMPTS - 1:
                    raise
                # 4, 8, 16, 32 s (with jitter): long enough to outlast a
                # per-minute rate-limit window across the default 5 attempts.
                await asyncio.sleep(min(4 * 2**attempt, 60) * random.uniform(0.75, 1.25))


def pass_rate(reports) -> float:
    # Paper Section 4: positive criteria pass when MET, negative ones when UNMET.
    passed = sum(
        (r.weight > 0 and r.verdict == "MET") or (r.weight < 0 and r.verdict == "UNMET")
        for r in reports
    )
    return passed / len(reports)


async def main() -> int:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    task = json.loads(TASK_FILE.read_text())
    sections = task["rubric"]["sections"]
    criteria = [(s["id"], c) for s in sections for c in s["criteria"]]

    content = REPORT_FILE.read_text(encoding="utf-8") if REPORT_FILE.exists() else ""
    if not content.strip():
        # Every positive criterion would be UNMET, so the clamped score is 0.
        print(f"No report found at {REPORT_FILE} (or it is empty); reward = 0")
        (VERIFIER_DIR / "reward.txt").write_text("0.0")
        return 0

    if ORACLE_MODE:
        # Pipeline check only (same approach as the clbench adapter): the report
        # was written and the rubric loads. No judge calls, so this says nothing
        # about grading correctness.
        if not criteria or not all(
            {"weight", "requirement"} <= c.keys() for _, c in criteria
        ):
            print("ORACLE_MODE: rubric in task.json is empty or malformed", file=sys.stderr)
            return 1
        print(f"ORACLE_MODE: report present ({len(content)} chars), {len(criteria)} criteria loaded; reward = 1")
        (VERIFIER_DIR / "reward.txt").write_text("1.0")
        return 0

    print(
        f"Judge: {JUDGE_MODEL} (temperature={JUDGE_TEMPERATURE or 'default'}, "
        f"reasoning_effort={JUDGE_REASONING_EFFORT or 'default'}); "
        f"report: {len(content)} chars; criteria: {len(criteria)}"
    )
    grader = PerCriterionGrader(generate_fn=generate)
    rubric = [Criterion(weight=c["weight"], requirement=c["requirement"]) for _, c in criteria]
    try:
        reports = await grader.judge(to_grade=content, rubric=rubric, query=task["problem"])
    except Exception as e:
        # A criterion that cannot be graded would silently change the score, so
        # fail the verifier instead of writing a partial reward.
        print(f"Grading failed after {JUDGE_MAX_ATTEMPTS} attempts: {e}", file=sys.stderr)
        return 1
    evaluation = await grader.aggregate(reports)

    with open(VERIFIER_DIR / "rubric_results.jsonl", "w") as f:
        for (section_id, criterion), report in zip(criteria, reports):
            f.write(
                json.dumps(
                    {
                        "section": section_id,
                        "id": criterion["id"],
                        "weight": criterion["weight"],
                        "requirement": criterion["requirement"],
                        "verdict": report.verdict,
                        "explanation": report.reason,
                    }
                )
                + "\n"
            )

    section_scores = {}
    for section in sections:
        section_reports = [r for (sid, _), r in zip(criteria, reports) if sid == section["id"]]
        section_scores[section["id"]] = (await grader.aggregate(section_reports)).score

    summary = {
        "normalized_score": evaluation.score,
        "raw_score": evaluation.raw_score,
        "pass_rate": pass_rate(reports),
        "section_scores": section_scores,
        "judge_model": JUDGE_MODEL,
        "judge_models_served": sorted(_models_served),
        "judge_temperature": JUDGE_TEMPERATURE or None,
        "judge_reasoning_effort": JUDGE_REASONING_EFFORT or None,
        "n_criteria": len(reports),
        "n_met": sum(r.verdict == "MET" for r in reports),
        "n_negative_met": sum(r.weight < 0 and r.verdict == "MET" for r in reports),
    }
    (VERIFIER_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    (VERIFIER_DIR / "reward.txt").write_text(str(evaluation.score))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
