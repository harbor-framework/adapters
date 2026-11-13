"""PaperFindingBench builder.

The agent is given a research query and must return a JSON blob of the form

    {"output": {"results": [{"paper_id": "<corpus_id>", "markdown_evidence": "..."}]}}

Scoring is a port of upstream's `score_paper_finder`
(astabench/evals/paper_finder/{task,eval,relevance,paper_finder_utils,datamodel}.py,
fork commit 17c84cab81cfaf87bbca0e11780803c3d6347ba6, eval code identical to
allenai/asta-bench main apart from the judge-model constant) and runs in the
Harbor verifier (`tests/run_scorer.py`) for EVERY agent, bridge or not:

  - Parsing: strict `json.loads` of the answer; on `JSONDecodeError` the
    upstream Haiku "repair" call; an `"error"` key / missing `"output"` /
    non-object top level is an upstream sample error (no reward here);
    all-or-nothing validation of `ExpectedAgentOutput` (invalid -> 0).
  - `specific_*` / `metadata_*` -> standard_f1 over the gold `corpus_ids`.
  - `semantic_*` -> adjusted_f1: papers in `known_to_be_good` are PERFECT,
    every other submitted paper is judged by `anthropic/claude-haiku-4-5`
    against the query's weighted `relevance_criteria` (4-level relevance),
    recall is `estimated_recall_at_estimate` over the normalizer
    `total_relevant`, combined with the lower-bound-corrected nDCG `rank`.
  - `litqa2_*` (sibling `litqa2_fulltext_search.py`) -> known_recall_at_30.

Upstream also consults a local `detailed_reference.json` judgement cache.
That file is not part of the dataset: it is created and mutated by each
upstream run, so a fresh install has none.  The port judges without it; the
upstream side of a parity run must delete its local copy first.

Oracle: specific/metadata/litqa2 oracles submit the gold list and score 1.0
through the real formula.  A semantic oracle cannot score 1.0 through the
formula (submitting only `known_to_be_good` makes every judgement PERFECT,
so `rank` degenerates to 0), so its payload carries the per-task
unforgeable nonce from `make_oracle_nonce()` and the scorer short-circuits
on it.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable
from pathlib import Path

from .base import (
    INSPECT_DEFAULT_EVAL_ARGS,
    VERIFIER_TEST_SH,
    BenchmarkBuilder,
    SampleRecord,
    make_inspect_config,
    make_oracle_nonce,
    wire_asta_mcp,
    write_task_files,
)

ASTA_BENCH_REVISION = "a600dc767f850385f4664772e3ba7a7f8be17d5e"

PF_INSERTED_BEFORE_YEAR = 2025
PF_INSERTED_BEFORE_MONTH = 6


def _release_date_tag() -> str:
    return f"{PF_INSERTED_BEFORE_YEAR}_{PF_INSERTED_BEFORE_MONTH - 1:02d}"


TASK_TOML_TEMPLATE = """\
schema_version = "1.0"

[task]
name = "{task_name}"
authors = [
    {{ name = "Allen Institute for AI (AstaBench)", email = "asta@allenai.org" }},
    {{ name = "AstaBench Paper-Finder family (arXiv:2510.21652)" }},
]
keywords = ["paper-finding", "retrieval", "literature-search"]

[metadata]
category = "literature-search"
family = "paper-finder"
split = "{split}"
source_sample_id = "{source_id}"

[agent]
timeout_sec = 1800

[verifier]
timeout_sec = 600

# The verifier calls anthropic/claude-haiku-4-5 (relevance judge for
# semantic queries; JSON-repair call for any non-JSON answer), exactly as
# upstream's scorer does.  The model is fixed in run_scorer.py like upstream.
[verifier.env]
ANTHROPIC_API_KEY = "${{ANTHROPIC_API_KEY:-}}"
ANTHROPIC_BASE_URL = "${{ANTHROPIC_BASE_URL:-}}"

[environment]
build_timeout_sec = 600.0
cpus = 1
memory_mb = 2048
storage_mb = 4096
# Internet genuinely required: the task is paper retrieval over Allen AI's
# live Asta corpus (ASTA_TOOL_KEY-gated MCP). There is no static answer
# source to leak — the corpus is the task.
allow_internet = true
"""


DOCKERFILE = """\
FROM python:3.12-slim

WORKDIR /app

# The verifier (tests/run_scorer.py) runs upstream's scorer, which makes LLM
# calls to anthropic/claude-haiku-4-5: the relevance judge for semantic
# queries and the JSON-repair call for answers that are not strict JSON.
# litellm (which brings pydantic/httpx) is pinned here so nothing is
# installed at verify time.  The inspect-solver bridge still installs
# astabench itself at runtime.
RUN pip install --no-cache-dir "litellm==1.82.3"
COPY workspace/inspect_config.json /app/inspect_config.json
"""


_FAMILY_TO_INSPECT_TASK = {
    "test": "astabench/paper_finder_test",
    "validation": "astabench/paper_finder_validation",
}


# Verbatim copy of astabench/evals/paper_finder/task.py::TASK_INSTRUCTIONS
# (fork commit 17c84ca), followed by the Harbor file-submission footer.
TASK_INSTRUCTIONS = """Find papers relevant to the following query: {query}
Try to be comprehensive in your search yet efficient and accurate, i.e. find as many highly relevant papers as possible, but try to keep efficiency in mind. You may submit up to 250 papers.
If the query asks for a specific paper known to the user, i.e. "the Transformer paper", "the BERT paper", "the GPT-3 paper" etc, try to find that specific paper and only return that one. This does not apply to any query phrased in singular "paper" or "article" - those can be general queries and should return multiple relevant papers, e.g. "which paper introduced a transformer-based generative model for text generation".

Return your answer as JSON with the following structure, results should be ordered by most relevant first:
```json
{{
    "output": {{
        "results": [
            {{
                "paper_id": "string; the semantic scholar corpus_id of the paper (a string of digits, not a sha)",
                "markdown_evidence": "string; markdown-formatted text taken verbatim from the paper that supports the relevance of the paper to the query; include all relevant context that will allow a reader to judge the paper's relevance without needing to look up additional information; this may be several sentences or several paragraphs depending on the paper and query, and you may include verbatim text from multiple parts of the paper if needed.  Always include the title and year of the paper at the start of the evidence."
            }},
            ...
        ]
    }}
}}
```
"""

SUBMISSION_FOOTER = """
# How to submit your answer

Write your final answer to `/app/answer.txt`: the JSON object described
above and nothing else.
"""

INSTRUCTION_TEMPLATE = TASK_INSTRUCTIONS + SUBMISSION_FOOTER


SOLVE_SH_TEMPLATE = """\
#!/bin/bash
set -e

cat > /app/answer.txt <<'ORACLE_ANSWER_EOF'
{oracle_answer}
ORACLE_ANSWER_EOF
"""


TEST_SH = VERIFIER_TEST_SH


# Port of upstream's paper_finder scorer.  Shared verbatim by the
# litqa2-fulltext-search family (query_type "litqa2").
RUN_SCORER_PY = r'''"""PaperFinder verifier: port of astabench's `score_paper_finder`.

Source: allenai/asta-bench, fork commit 17c84cab81cfaf87bbca0e11780803c3d6347ba6
(eval code identical to upstream main except the judge-model constants):
  astabench/evals/paper_finder/task.py               score_paper_finder
  astabench/evals/paper_finder/paper_finder_utils.py get_model_json_output,
                                                     take_top_results
  astabench/evals/paper_finder/eval.py               get_llm_relevance,
                                                     calc_standard_f1,
                                                     calc_adjusted_f1, ...
  astabench/evals/paper_finder/relevance.py          LLM relevance judge
  astabench/evals/paper_finder/datamodel.py          ExpectedAgentOutput
  astabench/evals/utils.py                           extract_json_from_response

Outcomes (see benchmarks/base.py verifier contract):
  * exit 0 + reward  -- a scored outcome (upstream returns a Score);
  * non-zero, no reward -- upstream raises (sample error), an LLM API
    failure, or a broken config.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from pathlib import Path

ANSWER_FILE = Path("/app/answer.txt")
CONFIG_FILE = Path("/tests/config.json")
REWARD_FILE = Path("/logs/verifier/reward.txt")

# paper_finder_utils.py
MAX_RESULTS_TO_CONSIDER = 250
# relevance.py::GRADER_MODEL_NAME and paper_finder_utils.py::parse_result_model.
GRADER_MODEL_NAME = "anthropic/claude-haiku-4-5"
PARSE_RESULT_MODEL_NAME = "anthropic/claude-haiku-4-5"

# Upstream calls get_model(<haiku>).generate(prompt) with no GenerateConfig.
# The model is not the eval's active model, so inspect_ai 0.3.203 merges only
# connection settings; AnthropicAPI.max_tokens_for_config() then supplies
# max_tokens=32000 (Claude 4.x default, under the 64k Haiku-4.5 cap) and no
# temperature / top_p / top_k / thinking is sent (API defaults apply).  The
# request below reproduces exactly that: one user message, max_tokens=32000.
JUDGE_MAX_TOKENS = 32000
# Transport/API errors: small bounded retry, then the verifier fails (no
# reward).  Inspect would retry indefinitely; an outage must never become a
# score.  Concurrency only bounds parallel requests (upstream gathers all).
API_NUM_RETRIES = 2
API_TIMEOUT_SEC = 120
JUDGE_CONCURRENCY = 16


# --- relevance.py --------------------------------------------------------
class Relevance:
    PERFECT = "perfectly_relevant_papers"
    HIGHLY = "highly_relevant_papers"
    SOMEWHAT = "somewhat_relevant_papers"
    NOT_RELEVANT = "not_relevant_papers"


pf_rj_2_bench_rj = {
    0: Relevance.NOT_RELEVANT,
    1: Relevance.SOMEWHAT,
    2: Relevance.HIGHLY,
    3: Relevance.PERFECT,
}
bench_rj_2_pf_rj = {v: k for k, v in pf_rj_2_bench_rj.items()}

rj_4l_codes = {
    "Perfectly Relevant": 3,
    "Highly Relevant": 2,
    "Somewhat Relevant": 1,
    "Not Relevant": 0,
}
_JUDGE_RELEVANCE_LITERALS = ("Perfectly Relevant", "Somewhat Relevant", "Not Relevant")

relevance_criteria_judgement_prompt_with_relevant_snippets_after = (
    """
Judge how relevant the following paper is to each of the provided criteria. For each criterion, consider its entire description when making your judgement.

For each criterion, provide the following outputs:
- `relevance` (str): one of "Perfectly Relevant", "Somewhat Relevant", "Not Relevant".
- `relevant_snippet` (str | null): a snippet from the document that best show the relevance of the paper to the criterion. To be clear, copy EXACT text ONLY. Choose one short text span that best shows the relevance in a concrete and specific way, up to 20 words. ONLY IF NECESSARY, you can add another few-words-long span (e.g. for coreference, disambiguation, necessary context), separated by ` ... `. If relevance is "Not Relevant" output null. The snippet may contain citations, but make sure to only take snippets that directly show the relevance of this paper."""
    # upstream line ends with a trailing space; kept explicit so editors
    # cannot strip it
    " "
    """

Also provide another field `relevance_summary` (str): a short summary explanation of how the paper is relevant to the criteria in general. null if it is not relevant to any of the criteria.
- This should be short but convey the most useful and specific information for a user skimming a list of papers, up to 30 words.
- No need to mention which are perfectly relevant, somewhat relevant, or not relevant. Just provide new information that was not mentioned in the criteria.
- Start with perfectly relevant ones, include a specific and interesting detail about what matches them. Then go on to somewhat relevant ones, saying why it is close but not a perfect match. No need to add extra info for not relevant ones.
- Start with actionable info. Instead of saying "The paper uses X to...", just say "Uses X to...".

Output a JSON:
- top-level key `criteria`. Under it, for every criterion name (exactly as given in the provided criteria), there should be an object containing two fields: `relevance` and `relevant_snippet`.
- top-level key `relevance_summary` with string value or null.

Criteria:
```
{criteria}
```"""
)  # noqa: E501

# --- paper_finder_utils.py ----------------------------------------------
# "previous_answer = " ends with a trailing space upstream (kept explicit).
parse_result_prompt = (
    "previous_answer = "
    """
```{previous_answer}```
output a json from the previous_answer like: dict("output" dict("results": [ dict("paper_id": .., "markdown_evidence": ...), ... ]))
dont surround the output with "```" i know its a json
"""
)


class AnswerFormatError(ValueError):
    """Upstream's caught `(json.JSONDecodeError, ValidationError)`: score 0."""


def _write_reward(value: float) -> None:
    REWARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    REWARD_FILE.write_text(f"{value:.6f}\n")


def _read_answer():
    # A missing file, a directory, or undecodable bytes is an invalid answer
    # (reward 0), never a verifier crash.  Bytes are decoded without newline
    # translation so the text equals the agent's completion exactly (it is
    # embedded verbatim in the repair prompt).
    try:
        if not ANSWER_FILE.is_file():
            return None
        return ANSWER_FILE.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"answer.txt unreadable: {e}", file=sys.stderr)
        return None


# --- LLM calls (litellm stands in for inspect's get_model().generate) ----
async def _generate(model: str, prompt: str) -> str:
    """Return the completion text; raise on any transport/API failure."""
    import litellm  # type: ignore

    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=JUDGE_MAX_TOKENS,
        num_retries=API_NUM_RETRIES,
        timeout=API_TIMEOUT_SEC,
    )
    if os.environ.get("ANTHROPIC_API_KEY"):
        kwargs["api_key"] = os.environ["ANTHROPIC_API_KEY"]
    if os.environ.get("ANTHROPIC_BASE_URL"):
        kwargs["api_base"] = os.environ["ANTHROPIC_BASE_URL"]
    resp = await litellm.acompletion(**kwargs)
    content = resp.choices[0].message.content
    if isinstance(content, list):
        content = "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    return content or ""


# --- astabench/evals/utils.py::extract_json_from_response (verbatim) -----
def extract_json_from_response(response: str):
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start == -1 or json_end == -1:
        return None

    try:
        return json.loads(response[json_start:json_end])
    except json.JSONDecodeError:
        try:
            return json.loads(response[json_start + 1 : json_end - 1])
        except json.JSONDecodeError:
            pass
        return None


# --- datamodel.py validation ----------------------------------------------
# Hand-written equivalent of pydantic v2 validation of
#   ExpectedAgentOutput(query_id: str | None = None, results: list[SingleResult])
#   SingleResult(paper_id: str, markdown_evidence: str)
# for json.loads-produced input (extra keys ignored; no int->str coercion).
# Kept dependency-free so the non-judge path runs without pydantic; the
# equivalence is pinned by tests/test_paper_finder_scorer.py against
# outcomes computed with upstream's pydantic models.
def _expected_agent_output(output) -> list[dict]:
    if not isinstance(output, dict):
        # `ExpectedAgentOutput(**output)` on a non-mapping: uncaught TypeError
        # upstream -> sample error.
        raise TypeError(f"argument after ** must be a mapping, not {type(output).__name__}")
    if "query_id" in output and not (
        output["query_id"] is None or isinstance(output["query_id"], str)
    ):
        raise AnswerFormatError("output.query_id must be a string or null")
    results = output.get("results")
    if not isinstance(results, list):
        raise AnswerFormatError("output.results must be a list")
    out = []
    for i, r in enumerate(results):
        if not isinstance(r, dict):
            raise AnswerFormatError(f"results[{i}] must be an object")
        for field in ("paper_id", "markdown_evidence"):
            if not isinstance(r.get(field), str):
                raise AnswerFormatError(f"results[{i}].{field} must be a string")
        out.append({"paper_id": r["paper_id"], "markdown_evidence": r["markdown_evidence"]})
    return out


# --- paper_finder_utils.py::get_model_json_output ------------------------
async def get_model_json_output(raw_output: str) -> list[dict]:
    try:
        json_output = json.loads(raw_output)
        if "error" in json_output:
            raise Exception(json_output["error"])
        output = json_output["output"]
    except json.JSONDecodeError:
        parse_result_prompt_filled = parse_result_prompt.format(
            previous_answer=raw_output
        )
        completion = await _generate(PARSE_RESULT_MODEL_NAME, parse_result_prompt_filled)
        try:
            output = json.loads(completion)["output"]
        except json.JSONDecodeError as e:
            raise AnswerFormatError(f"repair output is not JSON: {e}") from e

    return _expected_agent_output(output)


# task.py
def normalize_corpus_id(corpus_id: str) -> str:
    return corpus_id.strip().lower().replace("corpusid:", "")


# --- relevance.py: LLM relevance judgement --------------------------------
def _relevance_judgement_output(obj) -> dict:
    """Equivalent of pydantic `RelevanceJudgementOutput(**obj)`.

    Raises TypeError / ValueError exactly where upstream's construction does
    (both are caught upstream and the document is skipped)."""
    if not isinstance(obj, dict):
        raise TypeError("argument after ** must be a mapping")
    criteria = obj.get("criteria")
    if not isinstance(criteria, dict):
        raise ValueError("criteria must be a dict")
    if "relevance_summary" not in obj or not (
        obj["relevance_summary"] is None or isinstance(obj["relevance_summary"], str)
    ):
        raise ValueError("relevance_summary must be present (string or null)")
    parsed = {}
    for name, value in criteria.items():
        if not isinstance(value, dict):
            raise ValueError(f"criteria[{name!r}] must be an object")
        if "relevant_snippet" not in value or not (
            value["relevant_snippet"] is None or isinstance(value["relevant_snippet"], str)
        ):
            raise ValueError("relevant_snippet must be present (string or null)")
        if not (
            isinstance(value.get("relevance"), str)
            and value["relevance"] in _JUDGE_RELEVANCE_LITERALS
        ):
            raise ValueError(f"invalid relevance label {value.get('relevance')!r}")
        parsed[name] = {
            "relevance": value["relevance"],
            "relevant_snippet": value["relevant_snippet"],
        }
    return {"criteria": parsed, "relevance_summary": obj["relevance_summary"]}


def _format_documents_for_relevance_judgement(documents, criteria_to_use) -> list[dict]:
    formatted_criteria = json.dumps(
        [{"name": r["name"], "description": r["description"]} for r in criteria_to_use],
        indent=2,
    )
    # RelevanceJudgementInput(document=..., criteria=..., doc_id=...): a
    # TypedDict, i.e. a plain dict in this key order.
    return [
        {
            "document": doc["markdown"],
            "criteria": formatted_criteria,
            "doc_id": doc["corpus_id"],
        }
        for doc in documents
    ]


def build_judge_prompts(documents, relevance_criteria) -> list[str]:
    # Upstream formats `{criteria}` with the whole per-document dict, so the
    # prompt carries its Python repr (document, criteria JSON, doc_id).
    return [
        relevance_criteria_judgement_prompt_with_relevant_snippets_after.format(
            criteria=doc_text
        )
        for doc_text in _format_documents_for_relevance_judgement(
            documents, relevance_criteria
        )
    ]


async def _llm_judge_relevance_with_criteria(documents, relevance_criteria) -> dict:
    prompts = build_judge_prompts(documents, relevance_criteria)
    if len(prompts) == 0:
        return dict()
    sem = asyncio.Semaphore(JUDGE_CONCURRENCY)

    async def one(prompt: str) -> str:
        async with sem:
            return await _generate(GRADER_MODEL_NAME, prompt)

    completions = await asyncio.gather(*(one(p) for p in prompts))
    relevance_judgement_results = dict()
    for raw, doc_id in zip(completions, [d["corpus_id"] for d in documents]):
        try:
            relevance_judgement_results[doc_id] = _relevance_judgement_output(
                extract_json_from_response(raw)
            )
        except (TypeError, ValueError):
            # lets skip a single doc's failure..
            continue
    return relevance_judgement_results


def _parse_relevance_judgement_results(relevance_judgement_results: dict) -> dict:
    id2relevance = dict()
    for doc_id, relevance_judgement in relevance_judgement_results.items():
        id2relevance[doc_id] = [
            {
                # NOTE: removing underscore as it's a common llm error for naming fields
                "name": criterion_name.replace("_", " "),
                "relevance": rj_4l_codes[judgement["relevance"]],
                "relevant_snippet": judgement["relevant_snippet"],
            }
            for criterion_name, judgement in relevance_judgement["criteria"].items()
        ]
    return id2relevance


def calculate_0_to_3_relevance(relevance_criteria_score: float) -> int:
    if relevance_criteria_score <= 0.25:
        return 0
    if relevance_criteria_score <= 0.67:
        return 1
    if relevance_criteria_score <= 0.99:
        return 2
    return 3


def calculate_relevance_criteria_score(relevance_criteria, judgements) -> float:
    criterion_name_to_weight = {}
    for criteria in relevance_criteria:
        criterion_name_to_weight[criteria["name"]] = criteria["weight"]

    score = 0
    for judgement in judgements:
        # relevance is 0-3; divide by 3 to normalize to a 0-1 score
        score += (
            criterion_name_to_weight[judgement["name"]] * judgement["relevance"] / 3
        )

    score = min(1.0, score)

    return score


def _build_relevance_judgement_results(entities, id2relevance, relevance_criteria) -> dict:
    results = dict()
    for doc in entities:
        rcj_result = id2relevance.get(doc["corpus_id"])
        if relevance_criteria is None or rcj_result is None:
            continue
        required_criteria_names = [criterion["name"] for criterion in relevance_criteria]
        judgement_criteria_names = [criterion["name"] for criterion in rcj_result]
        if any(name not in judgement_criteria_names for name in required_criteria_names):
            continue
        try:
            relevance_criteria_score = calculate_relevance_criteria_score(
                relevance_criteria, rcj_result
            )
        except Exception:
            continue
        results[doc["corpus_id"]] = calculate_0_to_3_relevance(relevance_criteria_score)
    return results


async def load_relevance_judgement(entities, relevance_criteria) -> dict:
    relevance_judgement_results = await _llm_judge_relevance_with_criteria(
        entities, relevance_criteria
    )
    id2relevance = _parse_relevance_judgement_results(relevance_judgement_results)
    relevance_judgements = _build_relevance_judgement_results(
        entities, id2relevance, relevance_criteria
    )
    return {cid: pf_rj_2_bench_rj[pf_rj] for cid, pf_rj in relevance_judgements.items()}


# --- eval.py --------------------------------------------------------------
async def get_llm_relevance(results, known_to_be_good, relevance_criteria) -> dict:
    # Upstream also reads a local, run-mutated `detailed_reference.json`
    # cache here; it is absent on a fresh install and is not ported.
    judgements = dict()
    to_judge = []
    for result in results:
        if result["paper_id"] in known_to_be_good:
            judgements[result["paper_id"]] = Relevance.PERFECT
        else:
            to_judge.append(
                {"corpus_id": result["paper_id"], "markdown": result["markdown_evidence"]}
            )
    if to_judge:
        new_judgements = await load_relevance_judgement(to_judge, relevance_criteria)
        judgements.update(new_judgements)
    return judgements


def count_relevant(judgements: dict, top_k_results: list | None = None) -> int:
    return len(
        [
            paper_id
            for paper_id, judgement in judgements.items()
            if Relevance.PERFECT == judgement
            and (not top_k_results or paper_id in top_k_results)
        ]
    )


def get_predefined_judgements(results, corpus_ids) -> dict:
    return {
        result["paper_id"]: (
            Relevance.PERFECT if result["paper_id"] in corpus_ids else Relevance.NOT_RELEVANT
        )
        for result in results
    }


def calc_recall_at_k(results, total_relevant, judgements, k_type: str) -> dict:
    to_return = dict()
    relevant_predictions = count_relevant(judgements)
    to_return["relevant_predictions_at_full"] = relevant_predictions
    to_return[f"{k_type}_recall_at_full"] = relevant_predictions / total_relevant
    for name, k in {"estimate": total_relevant, "30": 30}.items():
        top_k_results = [
            result["paper_id"] for result in results if result["paper_id"] in judgements.keys()
        ][:k]
        relevant_predictions_at_k = count_relevant(judgements, top_k_results)
        to_return[f"{k_type}_recall_at_{name}"] = relevant_predictions_at_k / total_relevant
    return to_return


def calc_precision(judgements: dict) -> dict:
    relevant_predictions = count_relevant(judgements)
    return {"precision": relevant_predictions / len(judgements) if len(judgements) else 0.0}


def find_dcg(element_list: list) -> float:
    score = 0.0
    for order, rank in enumerate(element_list, 1):
        score += float(rank) / math.log(order + 1)
    return score


def lower_bound_corrected_ndcg(hypothesis: list) -> dict:
    max_dcg = find_dcg(sorted(hypothesis, reverse=True))
    min_dcg = find_dcg(sorted(hypothesis))
    return {
        "rank": (
            ((find_dcg(hypothesis) - min_dcg) / (max_dcg - min_dcg))
            if (max_dcg - min_dcg)
            else 0.0
        )
    }


def _calc_any_f(f_elements: list) -> float:
    return (
        (len(f_elements) / sum([(1 / element) for element in f_elements]))
        if all(f_elements)
        else 0.0
    )


def calc_adjusted_f1(results, total_relevant, judgements, k_type, k_value) -> dict:
    recall = calc_recall_at_k(results, total_relevant, judgements, k_type)
    rank = lower_bound_corrected_ndcg([bench_rj_2_pf_rj[j] for j in judgements.values()])
    f1 = _calc_any_f([rank["rank"], recall[f"{k_type}_recall_at_{k_value}"]])
    return {"adjusted_f1": f1, **recall, **rank}


def calc_standard_f1(results, total_relevant, judgements, k_type, k_value) -> dict:
    recall = calc_recall_at_k(results, total_relevant, judgements, k_type)
    precision = calc_precision(judgements)
    f1 = _calc_any_f([precision["precision"], recall[f"{k_type}_recall_at_{k_value}"]])
    return {"standard_f1": f1, **recall, **precision}


# --- Harbor-only: oracle nonce --------------------------------------------
def _submitted_oracle_marker(raw: str) -> str:
    try:
        obj = json.loads(raw)
    except (ValueError, RecursionError):
        return ""
    try:
        marker = obj["output"]["results"][0]["_oracle_marker"]
    except (KeyError, IndexError, TypeError):
        return ""
    return marker if isinstance(marker, str) else ""


# --- task.py::score_paper_finder ------------------------------------------
async def score(raw: str, cfg: dict) -> tuple[float, dict]:
    query_type = cfg["query_type"]
    if query_type not in ("specific", "metadata", "litqa2", "semantic"):
        # Our own config is corrupt (upstream derives it from the sample id).
        raise ValueError(f"Unsupported query_type {query_type!r}")
    total_relevant = cfg["total_relevant"]  # normalizer_reference[query_id]

    try:
        results = await get_model_json_output(raw)
        for res in results:
            res["paper_id"] = normalize_corpus_id(res["paper_id"])
    except (json.JSONDecodeError, AnswerFormatError) as e:
        print(f"Agent output has an invalid format: {e}", file=sys.stderr)
        return 0.0, {}
    results = results[:MAX_RESULTS_TO_CONSIDER]  # take_top_results

    if query_type in ("specific", "metadata", "litqa2"):
        judgements = get_predefined_judgements(results, cfg["gold_corpus_ids"])
        k_type = "known"
        k_value = "30" if query_type == "litqa2" else "full"
        sample_scores = calc_standard_f1(results, total_relevant, judgements, k_type, k_value)
    else:
        judgements = await get_llm_relevance(
            results, cfg["gold_corpus_ids"], cfg["relevance_criteria"]
        )
        k_type = "estimated"
        k_value = "estimate"
        sample_scores = calc_adjusted_f1(results, total_relevant, judgements, k_type, k_value)

    final_score_name = [k for k in sample_scores.keys() if "f1" in k][0]
    if query_type == "litqa2":
        final_score_name = f"{k_type}_recall_at_{k_value}"
    return float(sample_scores[final_score_name]), sample_scores


def main() -> int:
    raw = _read_answer()
    if raw is None:
        print("answer.txt missing or unreadable", file=sys.stderr)
        _write_reward(0.0)
        return 0
    cfg = json.loads(CONFIG_FILE.read_text())

    # Harbor-only oracle short-circuit (semantic queries only): the per-task
    # nonce lives in solve.sh and config.json, neither of which is in the
    # agent image.  Specific/metadata/litqa2 oracles go through the formula.
    expected_marker = cfg.get("oracle_marker") or ""
    if (
        cfg.get("query_type") == "semantic"
        and expected_marker
        and _submitted_oracle_marker(raw) == expected_marker
    ):
        print("oracle marker matched", file=sys.stderr)
        _write_reward(1.0)
        return 0

    value, metrics = asyncio.run(score(raw, cfg))
    print(f"metrics={json.dumps(metrics)} score={value:.6f}", file=sys.stderr)
    _write_reward(value)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # sample error / API failure / broken config
        print(f"verifier error (no reward): {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
'''


def _query_type(query_id: str) -> str:
    return query_id.split("_")[0]


def _headline_for(qtype: str) -> str:
    if qtype == "litqa2":
        return "known_recall_at_30"
    if qtype in ("specific", "metadata"):
        return "standard_f1"
    if qtype == "semantic":
        return "adjusted_f1"
    raise ValueError(f"Unknown query_type {qtype}")


def _gold_corpus_ids(qtype: str, scorer_criteria: dict) -> list[str]:
    """Gold list the scorer needs (and the oracle submits)."""
    if qtype in ("specific", "metadata", "litqa2"):
        return [str(c) for c in scorer_criteria.get("corpus_ids") or []]
    if qtype == "semantic":
        return [str(c) for c in scorer_criteria.get("known_to_be_good") or []]
    raise ValueError(f"Unknown query_type {qtype}")


def _relevance_criteria(scorer_criteria: dict) -> list[dict]:
    """Per-query weighted criteria the semantic relevance judge scores against
    (upstream BroadScorerCriteria.relevance_criteria, in dataset order)."""
    return [
        {
            "name": str(c["name"]),
            "description": str(c["description"]),
            "weight": float(c["weight"]),
        }
        for c in scorer_criteria.get("relevance_criteria") or []
    ]


def _load_normalizer_reference(token: str | None) -> dict[str, int]:
    """Mirror astabench's normalizer_reference fetch + factor inflation.

    Upstream applies a `get_factor`-based multiplier to `semantic_*` perfect
    counts (factor in [MIN_FACTOR=2, MAX_FACTOR=10]).  Specific/metadata
    counts are used as-is.
    """
    from huggingface_hub import hf_hub_download

    cached_path = hf_hub_download(
        repo_id="allenai/asta-bench",
        filename="tasks/paper_finder_bench/normalizer_reference.json",
        repo_type="dataset",
        revision=ASTA_BENCH_REVISION,
        token=token,
    )
    raw = json.loads(Path(cached_path).read_text(encoding="utf-8"))

    MAX_FACTOR = 10
    MIN_FACTOR = 2
    out: dict[str, int] = {}
    for qid, perfect_count in raw.items():
        if not perfect_count or perfect_count <= 0:
            continue
        if qid.startswith("semantic"):
            factor = (
                max(float(MIN_FACTOR), 2 / math.log(perfect_count))
                if perfect_count > 1
                else float(MAX_FACTOR)
            )
            out[qid] = math.ceil(perfect_count * factor)
        else:
            out[qid] = int(perfect_count)
    return out


class PaperFinderBuilder(BenchmarkBuilder):
    family_name = "paper-finder"
    default_split = "test"

    def _inspect_workspace_files(self, sample_id: str, split: str) -> dict[str, str]:
        cfg = make_inspect_config(
            task=_FAMILY_TO_INSPECT_TASK[split],
            sample_id=sample_id,
            pip_install=self.inspect_pip_install(),
            # Asta MCP literature search is a TASK arg (consumed by
            # `paper_finder()` upstream task constructor), not a solver arg.
            task_args={"with_search_tools": "1"},
            eval_args=INSPECT_DEFAULT_EVAL_ARGS,
        )
        return {"inspect_config.json": json.dumps(cfg, indent=2)}

    def load_samples(self, split: str) -> Iterable[SampleRecord]:
        from datasets import load_dataset

        if split not in {"validation", "test"}:
            raise ValueError(f"paper-finder: unknown split {split!r}")

        token = os.getenv("HF_TOKEN") or os.getenv("HF_ACCESS_TOKEN")
        release = _release_date_tag()
        ds = load_dataset(
            "allenai/asta-bench",
            data_files=f"tasks/paper_finder_bench/{split}_{release}.json",
            token=token,
            revision=ASTA_BENCH_REVISION,
        )
        rows = list(map(dict, ds["train"]))

        normalizer = _load_normalizer_reference(token)

        for row in rows:
            inp = row.get("input") or {}
            criteria = row.get("scorer_criteria") or {}
            query_id = str(inp.get("query_id") or "")
            # Upstream formats the raw query (no stripping) into the prompt.
            query_text = str(inp.get("query") or "")
            if not query_id or not query_text.strip():
                continue

            qtype = _query_type(query_id)
            if qtype not in ("specific", "metadata", "semantic"):
                # `litqa2_*` queries live in this dataset only on the
                # litqa2 splits, which our litqa2-fulltext-search builder
                # handles.  Anything else is unexpected; skip.
                continue

            if normalizer.get(query_id) is None:
                # Upstream's calc_recall_at_k divides by this; a missing
                # entry is a sample error there.  Fail generation loudly.
                raise ValueError(f"paper-finder: no normalizer entry for {query_id}")

            yield SampleRecord(
                sample_id=query_id,
                split=split,
                instruction=query_text,
                target=_gold_corpus_ids(qtype, criteria),
                metadata={
                    "query_type": qtype,
                    "relevance_criteria": (
                        _relevance_criteria(criteria) if qtype == "semantic" else []
                    ),
                    "total_relevant": normalizer[query_id],
                },
                workspace_files=self._inspect_workspace_files(query_id, split),
            )

    def write_task(self, record: SampleRecord, task_dir: Path) -> None:
        qtype = record.metadata["query_type"]
        gold: list[str] = list(record.target)

        instruction = INSTRUCTION_TEMPLATE.format(query=record.instruction)

        oracle_results = [
            {
                "paper_id": cid,
                "markdown_evidence": "Oracle reference (gold corpus id from AstaBench).",
            }
            for cid in gold
        ]
        oracle_marker = None
        if qtype == "semantic":
            # The formula cannot give a semantic oracle 1.0 (see module
            # docstring); carry the unforgeable per-task nonce instead.
            oracle_marker = make_oracle_nonce()
            if not oracle_results:
                oracle_results = [
                    {
                        "paper_id": "",
                        "markdown_evidence": "Oracle reference (no cached gold).",
                    }
                ]
            oracle_results[0]["_oracle_marker"] = oracle_marker
        oracle_payload = {"output": {"results": oracle_results}}
        solve_sh = SOLVE_SH_TEMPLATE.format(
            oracle_answer=json.dumps(oracle_payload, indent=2)
        )

        tests_config = {
            "family": self.family_name,
            "source_sample_id": record.sample_id,
            "split": record.split,
            "query_id": record.sample_id,
            "query_type": qtype,
            "headline_metric": _headline_for(qtype),
            # specific/metadata: SpecificPaperScorerCriteria.corpus_ids;
            # semantic: BroadScorerCriteria.known_to_be_good.
            "gold_corpus_ids": gold,
            "relevance_criteria": record.metadata["relevance_criteria"],
            "total_relevant": record.metadata["total_relevant"],
        }
        if oracle_marker is not None:
            tests_config["oracle_marker"] = oracle_marker

        task_name = f"allenai/asta-bench__{self.task_id(record)}"
        task_toml = TASK_TOML_TEMPLATE.format(
            task_name=task_name,
            split=record.split,
            source_id=record.sample_id,
        )

        write_task_files(
            task_dir,
            task_toml=task_toml,
            instruction_md=instruction,
            dockerfile=DOCKERFILE,
            solve_sh=solve_sh,
            test_sh=TEST_SH,
            tests_config=tests_config,
            extra_tests={"run_scorer.py": RUN_SCORER_PY},
            workspace_files=record.workspace_files,
        )

        wire_asta_mcp(task_dir)
