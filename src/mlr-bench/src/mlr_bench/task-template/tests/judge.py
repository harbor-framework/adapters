"""
MLR-Bench verifier: the official MLR-Judge end-to-end evaluator.

The rubric, prompt assembly, JSON extraction, required-key check and retry
count are copied verbatim from upstream ``mlrbench/evals/overall_review.py``
and ``mlrbench/utils/utils.py`` at commit ``fdf1fc52748444cbf25f986981c815aeaee21c93``
(https://github.com/chchenhui/mlrbench). The reviewer runs at temperature 0,
as upstream's ``create_lmm_client(..., judge_mode=True)`` does.
``parity_runner.py`` checks the vendored rubric against the upstream checkout
before every run.

Upstream scores Clarity, Novelty, Soundness, Significance and Overall on a
1-10 scale, plus a 1-5 Confidence. The Harbor reward is the official Overall
score mapped linearly onto [0, 1]:

    reward = (Overall - 1) / 9

The full review (all aspects, justifications, strengths and weaknesses) is
written to /logs/verifier/review.json.

Failure handling, which parity_runner.py applies identically on the original
side:
  * The paper is missing or empty: the agent produced nothing, so the reward
    is 0.0.
  * The judge fails or returns an incomplete or out-of-range review after all
    retries: no reward is written and the script exits non-zero, so Harbor
    records a verifier error rather than a score. Missing fields are never
    filled with minimum scores.

Reads:
  task_description.md            the workshop task (shipped next to this script
                                 with the verifier tests; never present in the
                                 agent's container)
  /workspace/research_output.md  the agent's paper

Writes:
  /logs/verifier/reward.txt      a float in [0, 1] (only when the review is valid)
  /logs/verifier/review.json     the judge's review
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

UPSTREAM_COMMIT = "fdf1fc52748444cbf25f986981c815aeaee21c93"

# Verbatim from upstream mlrbench/evals/overall_review.py (OVERALL_RUBRIC).
OVERALL_RUBRIC = """
You are an expert machine learning researcher!
You will be given a research paper which is based on a task description.
You might also be given the code of the paper to check the reproducibility of the paper. 
You task is to review the paper in terms of 4 key aspects - Clarity, Novelty, Soundness and Significance.
Please provide a score from 1 to 10 for each aspect and an overall assessment, where 1 is the lowest and 10 is the highest. Lastly, provide a confidence score from 1 to 5 for the overall assessment, where 1 is the lowest and 10 is the highest.

## Evaluation Rubric

1. Clarity (1-10)
    - Is the paper well-written and easy to understand?
    - Are the ideas and contributions clearly articulated?
    - Is the structure of the paper logical and coherent?

    9-10 - The paper is exceptionally well-written, with clear and concise language. The ideas are presented in a logical and coherent manner, making it easy to follow the author's arguments.
    7-8 - The paper is well-written, but there are some areas that could be improved for clarity. The ideas are mostly clear, but there may be some minor issues with the structure or language.
    5-6 - The paper is somewhat difficult to read, with several areas that are unclear or poorly articulated. The structure may be confusing, making it hard to follow the author's arguments.
    3-4 - The paper is poorly written, with many unclear or confusing sections. The ideas are not well-articulated, and the structure is disorganized.
    1-2 - The paper is extremely difficult to read, with numerous unclear or confusing sections. The ideas are poorly articulated, and the structure is completely disorganized.

2. Novelty (1-10)
    - Does the paper present new and original ideas and findings?
    - Are the experimental results and contributions original and novel?
    - Is the work a significant advance over existing research?

    9-10 - The paper presents groundbreaking ideas and findings that are highly original and significant. The contributions are a major advance over existing research and are likely to have a lasting impact on the field.
    7-8 - The paper presents some new and original ideas, and the contributions are significant. The work is a notable advance over existing research, but it may not be as groundbreaking as top-tier papers.
    5-6 - The paper presents some new ideas and findings, but they are not particularly original or significant. The contributions are somewhat incremental and do not represent a major advance over existing research.
    3-4 - The paper presents few new ideas or findings, and those that are presented are not original or significant. The contributions are minimal and do not advance the field.
    1-2 - The paper presents no new ideas, and the contributions are completely unoriginal. The work does not advance the field in any meaningful way.

3. Soundness (1-10)
    - Are the methods and techniques used in the paper sound and appropriate?
    - Are the results and conclusions supported by the data?
    - Are there any major flaws or weaknesses in the experimental design, results or analysis?
    - Are the experimental results reliable and consistent to the code of the paper? Are the experimental results real or fake?
    - Are the visualization and analysis figures based on real experimental results or based on fake data? 

    9-10 - The methods and techniques used in the paper are sound and appropriate. The results are well-supported by the data, and there are no major flaws or weaknesses in the experimental design, results or analysis. The experimental results are fully reliable and consistent with the code of the paper.
    7-8 - The methods and techniques used in the paper are mostly sound, but there may be some minor issues. The results are generally well-supported by the data, but there may be some areas that could be improved. The experimental design, results or analysis may have some minor flaws. The experimental results are mostly reliable.
    5-6 - The methods and techniques used in the paper are somewhat questionable, with several areas that could be improved. The results are not well-supported by the data, and there may be some significant flaws in the experimental design, results or analysis. Some experimental results are not reliable.
    3-4 - The methods and techniques used in the paper are flawed or inappropriate. The results are not well-supported by the data, and there are major flaws in the experimental design, results or analysis. Most of experimental results are not reliable.
    1-2 - The methods and techniques used in the paper are completely unsound. The results are not supported by the data, and there are numerous major flaws in the experimental design, results or analysis. The conclusions drawn from the paper are completely invalid. All experimental results are not reliable.

4. Significance (1-10)
    - Does the paper address an important problem or question?
    - Are the contributions significant to the field?
    - Are the experimental results reproducible and reliable? Do they have a significant impact?
    - Will the work have a lasting impact on the field?

    9-10 - The paper addresses a highly important problem or question, and the results and contributions are significant to the field. The work is likely to have a lasting impact on the field.
    7-8 - The paper addresses an important problem or question, and the results and contributions are significant. The work may have a lasting impact on the field, but it may not be as groundbreaking as top-tier papers.
    5-6 - The paper addresses a somewhat important problem or question, but the results and contributions are not particularly significant. The work may have some impact on the field, but it is unlikely to be lasting.
    3-4 - The paper addresses a minor problem or question, and the results and contributions are minimal. The work is unlikely to have any significant impact on the field.
    1-2 - The paper addresses an unimportant problem or question, and the results and contributions are completely insignificant. The work will have no impact on the field.

5. Overall Assessment (1-10)
    - Based on the above criteria, how would you rate the overall quality of the paper? Note that any single weakness can be critical to lower the overall assessment.
    - Is the paper suitable for publication in a top-tier conference or journal?
    - Would you recommend this paper to your colleagues?

    10 - The paper is of exceptional quality and is highly suitable for publication in a top-tier conference or journal. I would strongly recommend this paper.
    8-9 - The paper is of high quality and is suitable for publication in a top-tier conference or journal. I would recommend this paper.
    6-7 - The paper is of good quality and is suitable for publication in a reputable conference or journal. I would recommend this paper with some reservations.
    4-5 - The paper is of acceptable quality but may not be suitable for publication in a top-tier conference or journal. I would recommend this paper with significant reservations.
    2-3 - The paper is of poor quality and is not suitable for publication in a top-tier conference or journal. I would not recommend this paper.
    1 - The paper is of extremely poor quality and is not suitable for publication in any conference or journal. I would strongly advise against recommending this paper.

6. Confidence Score (1-5)
    - How confident are you in your overall assessment of the paper?

    5 - Extremely confident in the overall assessment.
    4 - Very confident in the overall assessment.
    3 - Moderately confident in the overall assessment.
    2 - Slightly confident in the overall assessment.
    1 - Not confident in the overall assessment.

Please provide a detailed review of the paper, including your scores for each aspect and an overall assessment. Be sure to justify your scores with specific examples from the paper.
Please do not include any personal opinions or biases in your review. Your review should be objective and based solely on the content of the paper. Please provide a confidence score from 1 to 5 for the overall assessment.
Do not hesitate to assign lower scores if the paper does not fully meet the criteria. Avoid giving high scores by default.

## Output Format

Please provide your review in the following format:

```json
{
    "Clarity": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Novelty": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Soundness": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Significance": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Overall": {
        "score": <1-10>,
        "strengths": ["<strength 1>", "<strength 2>"],
        "weaknesses": ["<weakness 1>", "<weakness 2>"]
    },
    "Confidence": <1-5>
}
```

Note that any single weakness can be critical to lower the overall assessment.
Please provide detailed justifications for each score, including specific examples from the paper. 
IMPORTANT: Please ensure that your output is a complete and valid JSON object and includes all the fields above. Do not output only a single item or partial content; you must output the entire JSON object.
"""

# Verbatim from upstream overall_review(): the f-string appended after the
# rubric. Placeholders are filled in a single pass (see build_prompt), so
# braces inside the task or paper stay inert.
_CONTEXT_TEMPLATE = """
## Task Description

```
{task}
```

## Paper to Be Reviewed
Note: The paper is generated by AI and may contain some errors. Please check the paper carefully and provide your review.
    
```json
{paper}
```

## Code of the Paper

```json
{code_content}
```
"""

# Verbatim from upstream overall_review(): the closing instructions appended
# after the context.
_CLOSING = """
Please provide a detailed review of the paper, including your scores for each aspect and an overall assessment. Be sure to justify your scores with specific examples from the paper.
Please do not include any personal opinions or biases in your review. Your review should be objective and based solely on the content of the paper. Please provide a confidence score from 1 to 5 for the overall assessment.
Do not hesitate to assign lower scores if the paper does not fully meet the criteria. Avoid giving high scores by default.
    
## Output Format

Please provide your review in the following format:

```json
{
    "Clarity": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Novelty": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Soundness": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Significance": {
        "score": <1-10>,
        "justification": "<Your justification here>"
    },
    "Overall": {
        "score": <1-10>,
        "strengths": ["<strength 1>", "<strength 2>"],
        "weaknesses": ["<weakness 1>", "<weakness 2>"]
    },
    "Confidence": <1-5>
}
```

Note that any single weakness can be critical to lower the overall assessment.
Please provide detailed justifications for each score, including specific examples from the paper. 
IMPORTANT: Please ensure that your output is a complete and valid JSON object and includes all the fields above. Do not output only a single item or partial content; you must output the entire JSON object.
"""

# Upstream overall_review(): required_keys.
REQUIRED_KEYS = [
    "Clarity",
    "Novelty",
    "Soundness",
    "Significance",
    "Overall",
    "Confidence",
]
ASPECTS = ["Clarity", "Novelty", "Soundness", "Significance", "Overall"]
# Upstream overall_review(max_retries=3).
MAX_RETRIES = 3
# Upstream create_lmm_client(max_tokens=8192 * 2, judge_mode=True).
MAX_TOKENS = 8192 * 2
TEMPERATURE = 0.0
REQUEST_TIMEOUT_SEC = 300.0

DEFAULT_JUDGE_MODEL = "anthropic/claude-haiku-4-5"


class JudgeError(RuntimeError):
    """The judge did not return a complete, valid review."""


def build_prompt(task: str, paper: str, code_content: str = "") -> str:
    """Assemble the review prompt exactly as upstream overall_review() does."""
    values = {"task": task, "paper": paper, "code_content": code_content}
    context = re.sub(
        r"\{(task|paper|code_content)\}",
        lambda m: values[m.group(1)],
        _CONTEXT_TEMPLATE,
    )
    return OVERALL_RUBRIC + context + _CLOSING


def extract_json_between_markers(llm_output):
    """Verbatim from upstream mlrbench/utils/utils.py."""
    # Extract content between markdown code block markers
    json_pattern = r"```json\s*(.*?)```"
    matches = re.findall(json_pattern, llm_output, re.DOTALL)

    if not matches:
        # Fallback: Try to find any JSON-like content in the output
        json_pattern = (
            r"\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}))*\}"
        )
        matches = re.findall(json_pattern, llm_output, re.DOTALL)

    for json_string in matches:
        # Clean up the string
        json_string = json_string.strip()

        # Pre-process LaTeX expressions - replace them with properly escaped versions
        def replace_latex(match):
            latex_content = match.group(1)
            # Double all backslashes to make them valid JSON escape sequences
            escaped_latex = latex_content.replace("\\", "\\\\")
            return escaped_latex

        # Replace LaTeX expressions ($...$) with their escaped content
        processed_json = re.sub(r"\$(.*?)\$", replace_latex, json_string)

        # Fix other common JSON issues
        # Fix trailing commas (valid in JS but not in JSON)
        processed_json = re.sub(r",(\s*[}\]])", r"\1", processed_json)

        # Remove invalid control characters
        processed_json = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", processed_json)

        try:
            # Try parsing the processed JSON
            parsed_json = json.loads(processed_json)
            return parsed_json
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            # If normal JSON parsing fails, try a different strategy
            try:
                # Remove all LaTeX expressions for a second attempt
                sanitized = re.sub(r"\$.*?\$", '""', processed_json)
                parsed_json = json.loads(sanitized)
                return parsed_json
            except json.JSONDecodeError as e2:
                print(f"Second JSON decode error: {e2}")
                # If both attempts fail, continue to the next match if any
                continue

    # If we reach here, no valid JSON was found or parsed successfully
    print("llm output:", llm_output)
    return None


def _integer_score(value: object, low: int, high: int, field: str) -> int:
    # bool is an int subclass; a JSON true/false is not a score.
    if isinstance(value, bool):
        raise ValueError(f"{field} is not a number: {value!r}")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(f"{field} is not an integer: {value!r}")
    if not low <= value <= high:
        raise ValueError(f"{field} = {value} is outside [{low}, {high}]")
    return value


def validate_review(review: object) -> dict:
    """Reject anything short of a complete review.

    Upstream checks that the response is a dict with every required key. This
    also checks that each score is present and in range, so an incomplete
    review is retried (and finally reported as a judge failure) instead of
    being scored.
    """
    if not isinstance(review, dict):
        raise ValueError("Response is not a dictionary")
    if not all(key in review for key in REQUIRED_KEYS):
        raise ValueError(f"Missing required keys. Found: {list(review.keys())}")
    for aspect in ASPECTS:
        entry = review[aspect]
        if not isinstance(entry, dict) or "score" not in entry:
            raise ValueError(f"{aspect} has no score: {entry!r}")
        _integer_score(entry["score"], 1, 10, f"{aspect}.score")
    _integer_score(review["Confidence"], 1, 5, "Confidence")
    return review


def reward_from_review(review: dict) -> float:
    overall = _integer_score(review["Overall"]["score"], 1, 10, "Overall.score")
    return round((overall - 1) / 9, 4)


def _call_judge(prompt: str, model: str) -> str:
    import litellm

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    api_base = os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    kwargs: dict = {
        "model": model,
        # Upstream sends the whole prompt as a single user message.
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "timeout": REQUEST_TIMEOUT_SEC,
        "api_key": api_key,
    }
    if api_base:
        kwargs["api_base"] = api_base
    response = litellm.completion(**kwargs)
    return response.choices[0].message.content or ""


def review_paper(task: str, paper: str, model: str | None = None) -> dict:
    """Run the official review with upstream's retry loop.

    Returns a validated review, or raises JudgeError after MAX_RETRIES
    failed attempts (API errors, unparseable or incomplete responses).
    """
    model = model or os.environ.get("MODEL_NAME") or DEFAULT_JUDGE_MODEL
    prompt = build_prompt(task, paper)
    errors: list[str] = []
    for attempt in range(MAX_RETRIES):
        try:
            response = _call_judge(prompt, model)
            review = extract_json_between_markers(response)
            return validate_review(review)
        except Exception as exc:
            print(f"Attempt {attempt + 1} failed: {exc}", file=sys.stderr)
            errors.append(f"{type(exc).__name__}: {exc}")
    raise JudgeError(f"All {MAX_RETRIES} judge attempts failed: {errors}")


def score_paper(
    task: str, paper: str | None, model: str | None = None
) -> tuple[float, dict | None]:
    """Score one paper. Shared by this verifier and parity_runner.py.

    Returns (reward, review). A missing or empty paper scores 0.0 with no
    review. Raises JudgeError when the judge cannot produce a valid review.
    """
    if paper is None or not paper.strip():
        return 0.0, None
    review = review_paper(task, paper, model)
    return reward_from_review(review), review


def main() -> int:
    # The task is read from the copy shipped with the verifier tests (same
    # directory as this script). It never exists in the agent's container.
    task_path = Path(__file__).resolve().parent / "task_description.md"
    paper_path = Path("/workspace/research_output.md")
    log_dir = Path("/logs/verifier")
    reward_path = log_dir / "reward.txt"
    review_path = log_dir / "review.json"
    log_dir.mkdir(parents=True, exist_ok=True)
    reward_path.unlink(missing_ok=True)

    if not task_path.exists():
        print(f"ERROR: verifier task description missing: {task_path}", file=sys.stderr)
        return 2
    task = task_path.read_text()
    paper = paper_path.read_text() if paper_path.exists() else None
    if paper is None:
        print(f"{paper_path} not found; reward = 0.0")
    elif not paper.strip():
        print(f"{paper_path} is empty; reward = 0.0")

    try:
        reward, review = score_paper(task, paper)
    except JudgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        review_path.write_text(
            json.dumps({"status": "judge_error", "error": str(exc)}, indent=2)
        )
        return 2

    if review is not None:
        review_path.write_text(json.dumps(review, indent=2))
        scores = {aspect: review[aspect]["score"] for aspect in ASPECTS}
        print(f"Scores: {scores}  Confidence: {review['Confidence']}")
        print(f"Overall {scores['Overall']}/10  ->  reward = {reward}")
    reward_path.write_text(str(reward))
    return 0


if __name__ == "__main__":
    sys.exit(main())
