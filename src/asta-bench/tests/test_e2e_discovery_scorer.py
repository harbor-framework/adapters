"""Offline fidelity tests for the e2e-bench / e2e-bench-hard verifier scorer.

The generated ``tests/run_scorer.py`` (``RUN_SCORER_PY``) is executed in-process
with a stub ``litellm`` whose responses are scripted per rubric question.

Every expected score below was produced by running the *real* upstream scorer
(allenai/asta-bench ``astabench/evals/e2e_discovery/task.py::score_rubric`` at
fork commit 17c84ca, inspect_ai 0.3.203) on the same answers with the same
scripted judge responses (``get_model`` patched to a fake returning
``ModelOutput.from_content([ContentText(...)])``), and pasted in as literals.
The prompt SHA-256 digests are of the prompts upstream sent to that fake.
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import json
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from asta_bench.benchmarks import e2e_discovery

MARKER = "asta-bench-oracle/" + "ab" * 24
QRE = re.compile(
    r"The specific rubric question you must evaluate is:\n```\n(.*?)\n```", re.DOTALL
)


# --------------------------------------------------------------------------
# Scenario fixtures (identical to those fed to upstream)
# --------------------------------------------------------------------------


def ev(paper=1, code=1, art=1, cons=1, overall=None, q="Q"):
    d = {
        "rubric_question": q,
        "standard": "s",
        "paper_evaluation": {
            "paper_evaluation_explanation": "p",
            "criteria_met": paper,
        },
        "code_evaluation": {"code_evaluation_explanation": "c", "criteria_met": code},
        "artifacts_evaluation": {
            "artifacts_evaluation_explanation": "a",
            "criteria_met": art,
        },
        "consistency_evaluation": {
            "consistency_evaluation_explanation": "x",
            "consistency_score": cons,
        },
    }
    if overall is not None:
        d["overall_evaluation"] = {
            "overall_evaluation_explanation": "o",
            "criteria_met": overall,
        }
    return d


def fenced(obj, prose="Thinking about it.\n"):
    return prose + "```json\n" + json.dumps(obj, indent=2) + "\n```\n"


def _without(d, key):
    return {k: v for k, v in d.items() if k != key}


RUBRIC = [
    {
        "criteria_name": f"c{i}",
        "criteria_met_question": f"Q{i}?",
        "required_or_optional": roo,
    }
    for i, roo in enumerate(
        [
            "required",
            "required",
            "required",
            "optional",
            "required",
            "required",
            "optional",
            "required",
        ]
    )
]

MIXED = {
    # plain JSON, overall pass
    "Q0?": [json.dumps(ev()), json.dumps(ev(overall=1))],
    # prose + fenced JSON, overall fail
    "Q1?": [fenced(ev()), fenced(ev(paper=0, overall=0))],
    # reflection lacks paper_evaluation -> skipped from the denominator
    "Q2?": [json.dumps(ev()), json.dumps(_without(ev(overall=1), "paper_evaluation"))],
    # optional, unparseable reflection -> None -> skipped
    "Q3?": [json.dumps(ev()), "no json here"],
    # non-numeric criteria_met -> comparison TypeError -> skipped
    "Q4?": [json.dumps(ev()), json.dumps(ev(paper="1", overall="1"))],
    # consistency 0 (with rubric_question); last fenced block wins
    "Q5?": [
        json.dumps(ev()),
        '```\n{"bad": \n```\n' + fenced(ev(cons=0, overall=1), prose=""),
    ],
    # optional pass
    "Q6?": [json.dumps(ev()), json.dumps(ev(overall=1))],
    # pass 1 unparseable -> reflection prompt == pass-1 prompt; pass 2 has
    # consistency 0 but no rubric_question -> KeyError -> skipped
    "Q7?": [
        "I cannot produce JSON right now.",
        json.dumps(_without(ev(cons=0, overall=1), "rubric_question")),
    ],
}

GOOD_ANSWER = json.dumps(
    {
        "results": {
            "report": "We did the experiment.",
            "code": [{"filename": "a.py", "code": "print(1)"}],
            "artifacts": [
                {"filename": "r.json", "format": "json", "artifact": '{"x": 1}'},
                {"filename": "log.txt", "format": "txt", "artifact": "y" * 10005},
            ],
        }
    }
)

ALL_PASS = {
    r["criteria_met_question"]: [json.dumps(ev()), json.dumps(ev(overall=1))]
    for r in RUBRIC
}
REQ_NONE = dict(ALL_PASS, **{"Q1?": [json.dumps(ev()), "nope"]})
REQ_NO_OVERALL = dict(ALL_PASS, **{"Q1?": [json.dumps(ev()), json.dumps(ev())]})
OPT_NO_OVERALL = dict(ALL_PASS, **{"Q3?": [json.dumps(ev()), json.dumps(ev())]})
NON_DICT = dict(ALL_PASS, **{"Q6?": ["[1, 2]", "7"]})

ANSWERS = {
    "good": GOOD_ANSWER,
    "prose": "Here is my answer: " + GOOD_ANSWER,
    "fenced": "```json\n" + GOOD_ANSWER + "\n```",
    "no_results": json.dumps({"report": "r", "code": [], "artifacts": []}),
    "paper_alias": json.dumps({"results": {"paper": "r"}}),
    "report_missing": json.dumps({"results": {"code": None, "artifacts": None}}),
    "report_int": json.dumps({"results": {"report": 5}}),
    "report_none": json.dumps({"results": {"report": None}}),
    "results_none": json.dumps({"results": None}),
    "results_list": json.dumps({"results": ["report"]}),
    "code_str": json.dumps({"results": {"report": "r", "code": "abc"}}),
    "code_empty_str": json.dumps({"results": {"report": "r", "code": ""}}),
    "code_entry_nonstr": json.dumps(
        {"results": {"report": "r", "code": [{"filename": "a", "code": 3}]}}
    ),
    "artifact_format_int": json.dumps(
        {
            "results": {
                "report": "r",
                "artifacts": [{"filename": "a", "format": 1, "artifact": "x"}],
            }
        }
    ),
    "artifact_nonstr_value": json.dumps(
        {
            "results": {
                "report": "r",
                "artifacts": [{"filename": "a", "artifact": {"k": 1}}],
            }
        }
    ),
    "list_answer": json.dumps(["results"]),
    "string_answer": json.dumps("results"),
    "null": "null",
    "empty_obj": "{}",
    "trailing_ws": GOOD_ANSWER + "\n\n",
}

# (upstream score, number of judge calls upstream made) -- from the upstream run.
EXPECTED_JUDGE_SCRIPTS = {
    "mixed": (MIXED, 0.6666666666666666, 16),
    "all_pass": (ALL_PASS, 1.0, 16),
    "required_response_none": (REQ_NONE, 0.0, 16),
    "required_missing_overall": (REQ_NO_OVERALL, 0.0, 16),
    "optional_missing_overall": (OPT_NO_OVERALL, 1.0, 16),
    "non_dict_judge_json": (NON_DICT, 1.0, 16),
}
EXPECTED_ANSWERS = {
    "good": (1.0, 16),
    "prose": (0.0, 0),
    "fenced": (0.0, 0),
    "no_results": (0.0, 0),
    "paper_alias": (1.0, 16),  # alias ignored: report defaults to "" and is judged
    "report_missing": (1.0, 16),
    "report_int": (0.0, 0),
    "report_none": (0.0, 0),
    "results_none": (0.0, 0),
    "results_list": (0.0, 0),
    "code_str": (0.0, 0),
    "code_empty_str": (1.0, 16),
    "code_entry_nonstr": (0.0, 0),
    "artifact_format_int": (0.0, 0),
    "artifact_nonstr_value": (1.0, 16),
    "list_answer": (0.0, 0),
    "string_answer": (0.0, 0),
    "null": (0.0, 0),
    "empty_obj": (0.0, 0),
    "trailing_ws": (1.0, 16),
}
UPSTREAM_PROMPT_SHA256 = {
    "Q0?": [
        "3f4c91624717db9ac415c68851446da812a4bd0e053e57213a6319367b327924",
        "335ff3da42efc803dfe556c130173b65e8b072ef95ecc7230024ba9b348892b4",
    ],
    "Q7?": [
        "6fb03819c51de5003d02a5459bb4add5e978cb132c3aede6f8a338bc5762c61b",
        "6fb03819c51de5003d02a5459bb4add5e978cb132c3aede6f8a338bc5762c61b",
    ],
}


# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------


class BadRequestError(Exception):
    """Shape of litellm.BadRequestError (status 400)."""

    status_code = 400


class Judge:
    """Stub litellm.acompletion scripted per rubric question."""

    def __init__(self, script, mode=None):
        self.script = script
        self.mode = mode
        self.counts = collections.Counter()
        self.prompts = collections.defaultdict(list)
        self.kwargs = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def acompletion(self, **kw):
        self.kwargs.append({k: v for k, v in kw.items() if k != "messages"})
        prompt = kw["messages"][0]["content"][0]["text"]
        q = QRE.search(prompt).group(1)
        i = self.counts[q]
        self.counts[q] += 1
        self.prompts[q].append(prompt)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.001)
        finally:
            self.in_flight -= 1
        if self.mode == "too_long":
            raise BadRequestError(
                'litellm.BadRequestError: AnthropicException - {"type":"error","error":'
                '{"type":"invalid_request_error","message":"prompt is too long: '
                '300000 tokens > 200000 maximum"}}'
            )
        if self.mode == "outage":
            raise ConnectionError("connection refused")
        text = self.script[q][i]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        )

    @property
    def calls(self):
        return sum(self.counts.values())


def run_scorer(
    tmp_path: Path, monkeypatch, answer: str | None, judge: Judge, rubric=RUBRIC
):
    stub = types.ModuleType("litellm")
    stub.acompletion = judge.acompletion
    monkeypatch.setitem(sys.modules, "litellm", stub)
    ns: dict = {"__name__": "run_scorer"}
    exec(compile(e2e_discovery.RUN_SCORER_PY, "run_scorer.py", "exec"), ns)  # noqa: S102
    ns["ANSWER_FILE"] = tmp_path / "answer.txt"
    ns["CONFIG_FILE"] = tmp_path / "config.json"
    ns["REWARD_FILE"] = tmp_path / "reward.txt"
    ns["CONFIG_FILE"].write_text(
        json.dumps({"oracle_marker": MARKER, "rubric": rubric})
    )
    if answer is not None:
        ns["ANSWER_FILE"].write_text(answer)
    rc = ns["main"]()
    assert rc == 0
    return float(ns["REWARD_FILE"].read_text()), ns


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(EXPECTED_JUDGE_SCRIPTS))
def test_score_matches_upstream_for_judge_responses(tmp_path, monkeypatch, name):
    script, expected, calls = EXPECTED_JUDGE_SCRIPTS[name]
    judge = Judge(script)
    reward, _ = run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge)
    assert reward == pytest.approx(expected, abs=1e-6)
    assert judge.calls == calls


@pytest.mark.parametrize("name", list(EXPECTED_ANSWERS))
def test_answer_parsing_matches_upstream(tmp_path, monkeypatch, name):
    expected, calls = EXPECTED_ANSWERS[name]
    judge = Judge(ALL_PASS)
    reward, _ = run_scorer(tmp_path, monkeypatch, ANSWERS[name], judge)
    assert reward == expected
    assert judge.calls == calls


def test_prompts_byte_identical_to_upstream(tmp_path, monkeypatch):
    judge = Judge(MIXED)
    run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge)
    for q, digests in UPSTREAM_PROMPT_SHA256.items():
        got = [hashlib.sha256(p.encode()).hexdigest() for p in judge.prompts[q]]
        assert got == digests, q


def test_mixed_denominator_breakdown(tmp_path, monkeypatch):
    """Q2 (missing field), Q4 (non-numeric), Q7 (KeyError on consistency
    message) are skipped; Q3/Q6 optional.  Required counted: Q0, Q1, Q5 ->
    2 / 3, not 3 / 6 as a count-every-required-criterion port would give."""
    judge = Judge(MIXED)
    reward, _ = run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge)
    assert reward == pytest.approx(2 / 3, abs=1e-6)


def test_prompt_too_long_scores_zero(tmp_path, monkeypatch):
    # Upstream (inspect_ai 0.3.203) turns "prompt is too long" into a string
    # ModelOutput, `content[0].text` raises, score_rubric catches -> 0.
    judge = Judge(ALL_PASS, mode="too_long")
    reward, _ = run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge)
    assert reward == 0.0
    assert judge.calls == len(RUBRIC)  # one (failed) pass-1 call per criterion


def test_judge_outage_raises_without_reward(tmp_path, monkeypatch):
    judge = Judge(ALL_PASS, mode="outage")
    with pytest.raises(Exception) as excinfo:
        run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge)
    assert type(excinfo.value).__name__ == "JudgeUnavailable"
    assert not (tmp_path / "reward.txt").exists()


def test_judge_parameters_match_upstream_effective_config(tmp_path, monkeypatch):
    judge = Judge(ALL_PASS)
    run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge)
    for kw in judge.kwargs:
        assert kw["model"] == "anthropic/claude-haiku-4-5"
        assert "temperature" not in kw and "top_p" not in kw
        assert kw["max_tokens"] == 32000
        assert kw["timeout"] == 300


def test_judge_concurrency_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("E2E_JUDGE_MAX_CONNECTIONS", "2")
    rubric = [
        {
            "criteria_name": f"c{i}",
            "criteria_met_question": f"Q{i}?",
            "required_or_optional": "required",
        }
        for i in range(12)
    ]
    script = {
        r["criteria_met_question"]: [json.dumps(ev()), json.dumps(ev(overall=1))]
        for r in rubric
    }
    judge = Judge(script)
    reward, _ = run_scorer(tmp_path, monkeypatch, GOOD_ANSWER, judge, rubric=rubric)
    assert reward == 1.0
    assert judge.max_in_flight == 2


def test_oracle_marker_short_circuits_without_judge(tmp_path, monkeypatch):
    judge = Judge(ALL_PASS)
    answer = json.dumps({"_oracle_marker": MARKER, "results": {"report": "x"}})
    reward, _ = run_scorer(tmp_path, monkeypatch, answer, judge)
    assert reward == 1.0 and judge.calls == 0


def test_wrong_oracle_marker_is_judged_normally(tmp_path, monkeypatch):
    judge = Judge(REQ_NONE)
    answer = json.dumps(
        {"_oracle_marker": "asta-bench-oracle/guess", "results": {"report": "x"}}
    )
    reward, _ = run_scorer(tmp_path, monkeypatch, answer, judge)
    assert reward == 0.0 and judge.calls == 16


def test_missing_answer_scores_zero(tmp_path, monkeypatch):
    judge = Judge(ALL_PASS)
    reward, _ = run_scorer(tmp_path, monkeypatch, None, judge)
    assert reward == 0.0 and judge.calls == 0
