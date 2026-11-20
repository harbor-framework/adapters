"""LLM-judge grader for FrontierScience-Research.

Follows ``inspect_evals/frontierscience`` (research format), which uses the judge
prompt from the FrontierScience paper (arXiv:2601.21165, Appendix B):

* the judge sees the problem, the 10-point rubric and the answer;
* the first ``VERDICT: <points>`` in the judge's reply is parsed; a reply with no
  parseable verdict scores 0 points;
* points are clamped to [0, 10];
* an empty or missing answer scores 0 without calling the judge.

It writes two rewards to /logs/verifier/reward.json:

* ``reward``: 1.0 if points >= 7 else 0.0 (the paper's success criterion);
* ``score``: points / 10 (the continuous metric reported by inspect_evals).

A judge refusal (``stop_reason == "refusal"``) or an API failure is not scored as 0:
the grader records it in grading.json and exits non-zero without a reward file, so
Harbor reports a verifier error for the trial.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic

TESTS_DIR = Path(__file__).resolve().parent
TASK_FILE = Path(os.environ.get("FS_TASK_FILE", TESTS_DIR / "task.json"))
ANSWER_FILE = Path(os.environ.get("FS_ANSWER_FILE", "/workspace/answer.md"))
VERIFIER_DIR = Path(os.environ.get("FS_VERIFIER_DIR", "/logs/verifier"))

JUDGE_MODEL = os.environ.get("JUDGE_MODEL") or "claude-sonnet-5-5"
JUDGE_EFFORT = os.environ.get("JUDGE_EFFORT", "high").strip()
JUDGE_MAX_TOKENS = int(os.environ.get("JUDGE_MAX_TOKENS", "64000"))
JUDGE_REFUSAL_RETRIES = int(os.environ.get("JUDGE_REFUSAL_RETRIES", "2"))

MAX_POINTS = 10.0
PASS_THRESHOLD = 7.0

# Verbatim from inspect_evals/frontierscience (RESEARCH_GRADING_TEMPLATE), which is the
# paper's Appendix B research judge prompt.
RESEARCH_GRADING_TEMPLATE = """
You are grading a science exam.
You will be given the problem, attempted answer, and a rubric to grade the answer. The rubric will total up to 10 points.
Evaluate the attempted answer against the provided rubric. Pay close attention to detail and grade it strictly, but fairly. Only evaluate against the rubric, as you yourself should not make any judgements (e.g., even if you think the answer is correct but rubric is wrong, you should treat the rubric as the gold standard). Return the absolute total number of points earned (it can be a decimal based on the rubric).
***
The problem: {problem}
***
The rubric: {rubric}
***
The attempted answer: {answer}
***
First, think step-by-step about each rubric item. Explain your reasoning for each rubric item.
Then, tally the points up and write VERDICT: <total_points> in the last line of your response, no other text. For example, VERDICT: 2.5 or VERDICT: 8.
""".strip()

VERDICT_RE = re.compile(r"VERDICT:\s*([\d.]+)", re.IGNORECASE)


def parse_points(text: str) -> float | None:
    """First VERDICT number in the reply, clamped to [0, 10]; None if unparseable."""
    match = VERDICT_RE.search(text)
    if not match:
        return None
    try:
        points = float(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(MAX_POINTS, points))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def write_rewards(points: float) -> dict[str, float]:
    rewards = {
        "reward": 1.0 if points >= PASS_THRESHOLD else 0.0,
        "score": points / MAX_POINTS,
    }
    write_json(VERIFIER_DIR / "reward.json", rewards)
    return rewards


def call_judge(prompt: str) -> tuple[anthropic.types.Message, list[dict]]:
    """Run the judge; retry refusals a few times. Returns the last message and refusals."""
    client = anthropic.Anthropic(max_retries=6, timeout=900.0)
    params: dict = {
        "model": JUDGE_MODEL,
        "max_tokens": JUDGE_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    if JUDGE_EFFORT:
        params["output_config"] = {"effort": JUDGE_EFFORT}

    refusals: list[dict] = []
    for attempt in range(1 + JUDGE_REFUSAL_RETRIES):
        with client.messages.stream(**params) as stream:
            message = stream.get_final_message()
        if message.stop_reason != "refusal":
            return message, refusals
        details = getattr(message, "stop_details", None)
        refusals.append(
            {
                "attempt": attempt + 1,
                "category": getattr(details, "category", None),
                "explanation": getattr(details, "explanation", None),
                "request_id": getattr(message, "_request_id", None),
            }
        )
        time.sleep(2 * (attempt + 1))
    return message, refusals


def main() -> int:
    task = json.loads(TASK_FILE.read_text())
    grading: dict = {
        "task_id": task.get("task_id"),
        "judge_model": JUDGE_MODEL,
        "judge_effort": JUDGE_EFFORT or None,
        "pass_threshold": PASS_THRESHOLD,
    }

    answer = ANSWER_FILE.read_text(errors="replace") if ANSWER_FILE.is_file() else ""
    grading["answer_chars"] = len(answer)
    if not answer.strip():
        rewards = write_rewards(0.0)
        grading.update(status="no_answer", points=0.0, **rewards)
        write_json(VERIFIER_DIR / "grading.json", grading)
        print(f"No answer at {ANSWER_FILE}; scored 0.")
        return 0

    prompt = RESEARCH_GRADING_TEMPLATE.format(
        problem=task["problem"], rubric=task["rubric"], answer=answer
    )

    try:
        message, refusals = call_judge(prompt)
    except anthropic.APIError as exc:
        grading.update(status="judge_error", error=f"{type(exc).__name__}: {exc}")
        write_json(VERIFIER_DIR / "grading.json", grading)
        print(f"Judge API error: {exc}", file=sys.stderr)
        return 3

    grading["refusals"] = refusals
    grading["served_model"] = message.model
    grading["stop_reason"] = message.stop_reason
    grading["usage"] = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
    judge_text = "".join(b.text for b in message.content if b.type == "text")
    grading["judge_response"] = judge_text

    if message.stop_reason == "refusal":
        grading["status"] = "judge_refused"
        write_json(VERIFIER_DIR / "grading.json", grading)
        print(
            f"Judge refused on all {len(refusals)} attempt(s): "
            f"{[r['category'] for r in refusals]}",
            file=sys.stderr,
        )
        return 2

    raw = parse_points(judge_text)
    points = 0.0 if raw is None else raw
    rewards = write_rewards(points)
    grading.update(
        status="graded" if raw is not None else "unparsed_verdict",
        points=points,
        **rewards,
    )
    write_json(VERIFIER_DIR / "grading.json", grading)
    print(
        f"{task.get('task_id')}: {points:g}/10 -> reward={rewards['reward']:g} "
        f"score={rewards['score']:.3f} (judge={message.model}, stop={message.stop_reason}"
        f"{', refusals=' + str(len(refusals)) if refusals else ''})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
