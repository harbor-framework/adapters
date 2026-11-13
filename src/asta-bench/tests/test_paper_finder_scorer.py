"""Offline equivalence tests for the paper-finder / litqa2-fulltext-search scorer.

The generated ``tests/run_scorer.py`` (``paper_finder.RUN_SCORER_PY``) is run
as a subprocess, exactly as ``test.sh`` runs it, against a stub ``litellm``
that returns canned judge / repair completions and logs every request.

Expected values were computed by running upstream's own
``astabench.evals.paper_finder.task.score_paper_finder`` (fork commit
17c84cab81cfaf87bbca0e11780803c3d6347ba6, inspect_ai 0.3.203) on the same
inputs, with ``get_model(...).generate`` replaced by the same canned
completions, ``check_verified`` / ``update_references`` stubbed out, an
empty ``detailed_reference`` cache and ``normalizer_reference`` set to the
case's ``total_relevant``.  "raise" means upstream raised (a sample error):
the Harbor verifier must exit non-zero without writing a reward.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from asta_bench.benchmarks import litqa2_fulltext_search as l2s
from asta_bench.benchmarks import paper_finder as pf
from asta_bench.benchmarks.base import SampleRecord


# --- fixed inputs (identical to those fed to upstream) ----------------------
def _res(pid, ev="evidence"):
    return {"paper_id": pid, "markdown_evidence": ev}


def _ans(results, **extra):
    return json.dumps({"output": {"results": results, **extra}})


def _jv(**crit):
    return json.dumps(
        {
            "criteria": {
                k.replace("__", " "): {"relevance": v, "relevant_snippet": None}
                for k, v in crit.items()
            },
            "relevance_summary": None,
        }
    )


P, S, N = "Perfectly Relevant", "Somewhat Relevant", "Not Relevant"
CRIT = [
    {
        "name": "Crit A",
        "description": 'Must use method "A" — with ünïcode.',
        "weight": 0.6,
    },
    {"name": "Crit B", "description": "Must evaluate on B's data.", "weight": 0.4},
]

CASES = {
    "specific_mixed": {
        "query_id": "specific_1",
        "total_relevant": 3,
        "gold": ["111", "222", "333"],
        "answer": _ans([_res("CorpusId:111"), _res("999"), _res(" 222 "), _res("111")]),
    },
    "metadata_exact_gold": {
        "query_id": "metadata_2",
        "total_relevant": 1,
        "gold": ["5"],
        "answer": _ans([_res("5")]),
    },
    "litqa2_recall_at_30": {
        "query_id": "litqa2_6",
        "total_relevant": 2,
        "gold": ["7", "8"],
        "answer": _ans(
            [_res(str(1000 + i)) for i in range(10)]
            + [_res("7")]
            + [_res(str(2000 + i)) for i in range(20)]
            + [_res("8")]
            + [_res(str(3000 + i)) for i in range(3)]
        ),
    },
    "specific_cap_250": {
        "query_id": "specific_3",
        "total_relevant": 1,
        "gold": ["42"],
        "answer": _ans([_res(str(10000 + i)) for i in range(250)] + [_res("42")]),
    },
    "semantic_judged": {
        "query_id": "semantic_9",
        "total_relevant": 3,
        "gold": ["100"],
        "criteria": CRIT,
        "answer": _ans(
            [
                _res(
                    "200",
                    "Title: Paper 200 (2020)\nIt's \"great\" — naïve 'quotes' \\ backslash",
                ),
                _res("100"),
                _res("300"),
                _res("400"),
                _res("500"),
                _res("600"),
                _res("700"),
                _res("800"),
                _res("200", "duplicate"),
            ]
        ),
        "judge": {
            "200": _jv(Crit__A=P, Crit__B=P),
            # underscore in the criterion name + JSON wrapped in prose/fences
            "300": "Here you go:\n```json\n" + _jv(Crit_A=P, Crit__B=S) + "\n```",
            "400": _jv(Crit__A="Highly Relevant", Crit__B=P),  # invalid label
            "500": _jv(Crit__A=P),  # missing criterion
            "600": "I cannot judge this.",  # no JSON
            "700": _jv(Crit__A=P, Crit__B=P),  # PERFECT beyond total_relevant
            "800": _jv(Crit__A=N, Crit__B=N),
        },
    },
    "semantic_exact_gold_set": {
        "query_id": "semantic_10",
        "total_relevant": 20,
        "gold": ["100", "101"],
        "criteria": CRIT,
        "answer": _ans([_res("100"), _res("101")]),
    },
    "semantic_somewhat_only": {
        "query_id": "semantic_11",
        "total_relevant": 4,
        "gold": [],
        "criteria": CRIT,
        "answer": _ans([_res("3"), _res("1"), _res("2")]),
        "judge": {
            "1": _jv(Crit__A=S, Crit__B=S),
            "2": _jv(Crit__A=P, Crit__B=N),
            "3": _jv(Crit__A=P, Crit__B=P),
        },
    },
    "p5_int_paper_id": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": json.dumps(
            {
                "output": {
                    "results": [
                        {"paper_id": "1", "markdown_evidence": "x"},
                        {"paper_id": 2, "markdown_evidence": "x"},
                    ]
                }
            }
        ),
    },
    "p5_missing_evidence": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": json.dumps({"output": {"results": [{"paper_id": "1"}]}}),
    },
    "p5_empty_id_counts": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": _ans([_res("1"), _res("")]),
    },
    "p5_query_id_int": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": _ans([_res("1")], query_id=5),
    },
    "empty_results": {
        "query_id": "semantic_12",
        "total_relevant": 4,
        "gold": ["1"],
        "criteria": CRIT,
        "answer": _ans([]),
    },
    "p6_error_key": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": json.dumps({"error": "boom"}),
    },
    "p6_missing_output": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": json.dumps({"results": []}),
    },
    "p6_top_level_list": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": "[1, 2, 3]",
    },
    "p6_output_is_list": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": json.dumps({"output": [_res("1")]}),
    },
    "p6_json_string_AB": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": json.dumps("AB"),
    },
    "deep_nesting": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": "[" * 100000 + "]" * 100000,
    },
    "repair_ok": {
        "query_id": "specific_1",
        "total_relevant": 2,
        "gold": ["1", "2"],
        "answer": "Final answer:\n```json\n" + _ans([_res("1"), _res("3")]) + "\n```\n",
        "repair": _ans([_res("1"), _res("3")]),
    },
    "repair_not_json": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": "no json here",
        "repair": "Sorry, I can't.",
    },
    "repair_no_output_key": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": "no json here",
        "repair": json.dumps({"results": []}),
    },
    "repair_empty_answer": {
        "query_id": "specific_1",
        "total_relevant": 1,
        "gold": ["1"],
        "answer": "",
        "repair": _ans([_res("1")]),
    },
}

# --- upstream outcomes (score_paper_finder, see module docstring) ---------
RAISE = "raise"
UPSTREAM = {
    "specific_mixed": 0.6666666666666666,
    "metadata_exact_gold": 1.0,
    "litqa2_recall_at_30": 0.5,
    "specific_cap_250": 0.0,
    "semantic_judged": 0.7888977060462431,
    "semantic_exact_gold_set": 0.0,
    "semantic_somewhat_only": 0.4,
    "p5_int_paper_id": 0.0,
    "p5_missing_evidence": 0.0,
    "p5_empty_id_counts": 0.6666666666666666,
    "p5_query_id_int": 0.0,
    "empty_results": 0.0,
    "p6_error_key": RAISE,  # Exception
    "p6_missing_output": RAISE,  # KeyError
    "p6_top_level_list": RAISE,  # TypeError
    "p6_output_is_list": RAISE,  # TypeError
    "p6_json_string_AB": RAISE,  # TypeError
    "deep_nesting": RAISE,  # RecursionError
    "repair_ok": 0.5,
    "repair_not_json": 0.0,
    "repair_no_output_key": RAISE,  # KeyError
    "repair_empty_answer": 1.0,
}

# sha256 of every prompt upstream sent to the (mocked) Haiku model, sorted.
UPSTREAM_PROMPT_SHA256 = {
    "semantic_judged": [
        "0843734aba6c4769a5581b7c09204faaeb76f7ef308b246ebec9864e4962f82b",
        "33661e716e40ce9b627f1656d5974fe5a619a64b80bf54ccded65cc18368c01b",
        "48d09ff4579cf7f14f5037f85310f392bceb7b8728c4ad6944811a02695edceb",
        "5003f189ee4e3ec4b10f54499a3d904595032e426ba01948984b5dfdbb71f2d2",
        "a154e2afe08d06efa9fdb0e9572a885f15f7ff360c58f995e77503e541d53812",
        "c580cb43b2d42a3ea7b48fbacd0603e028e4cbd931df061e99c4fcec8a7154e2",
        "e4c55a04cec94bc346770e89a9568373f8738f09ee1f32d0782e21993902c363",
        "ff1ae2edea53a3dd40022707579b5b97583defe19b7a27d39b40520834342027",
    ],
    "semantic_somewhat_only": [
        "2360aaabbca7a7ebc7c397a2e1ca0c14fd0c4df398f1a7026e94179e9ac6b0c3",
        "2fc76710bfeea59a65937703a94fa72e6d852191f1f89bd1ee655f76fd6eb661",
        "6c68f5e2f10db5ca311ace3a075192d6bc8433725e133ae1acae7c9d75427af0",
    ],
    "repair_ok": ["5f6a16278aeb268b33b57892286eb5b1f6030630687890bf16fa5f4225b08704"],
    "repair_not_json": [
        "3c4afdf2e31ea18026282ec441874d71a4290715b8bc519d42947aa798b61d68"
    ],
    "repair_no_output_key": [
        "3c4afdf2e31ea18026282ec441874d71a4290715b8bc519d42947aa798b61d68"
    ],
    "repair_empty_answer": [
        "b1702860b371ac254124bdff27d21d9eb357b64d3bf683bb4ba4823ba954d73b"
    ],
}

# The full upstream judge prompt for doc 200 of "semantic_judged" (JSON-encoded).
UPSTREAM_PROMPT_DOC_200 = json.loads(
    r'''"\nJudge how relevant the following paper is to each of the provided criteria. For each criterion, consider its entire description when making your judgement.\n\nFor each criterion, provide the following outputs:\n- `relevance` (str): one of \"Perfectly Relevant\", \"Somewhat Relevant\", \"Not Relevant\".\n- `relevant_snippet` (str | null): a snippet from the document that best show the relevance of the paper to the criterion. To be clear, copy EXACT text ONLY. Choose one short text span that best shows the relevance in a concrete and specific way, up to 20 words. ONLY IF NECESSARY, you can add another few-words-long span (e.g. for coreference, disambiguation, necessary context), separated by ` ... `. If relevance is \"Not Relevant\" output null. The snippet may contain citations, but make sure to only take snippets that directly show the relevance of this paper. \n\nAlso provide another field `relevance_summary` (str): a short summary explanation of how the paper is relevant to the criteria in general. null if it is not relevant to any of the criteria.\n- This should be short but convey the most useful and specific information for a user skimming a list of papers, up to 30 words.\n- No need to mention which are perfectly relevant, somewhat relevant, or not relevant. Just provide new information that was not mentioned in the criteria.\n- Start with perfectly relevant ones, include a specific and interesting detail about what matches them. Then go on to somewhat relevant ones, saying why it is close but not a perfect match. No need to add extra info for not relevant ones.\n- Start with actionable info. Instead of saying \"The paper uses X to...\", just say \"Uses X to...\".\n\nOutput a JSON:\n- top-level key `criteria`. Under it, for every criterion name (exactly as given in the provided criteria), there should be an object containing two fields: `relevance` and `relevant_snippet`.\n- top-level key `relevance_summary` with string value or null.\n\nCriteria:\n```\n{'document': 'Title: Paper 200 (2020)\\nIt\\'s \"great\" \u2014 na\u00efve \\'quotes\\' \\\\ backslash', 'criteria': '[\\n  {\\n    \"name\": \"Crit A\",\\n    \"description\": \"Must use method \\\\\"A\\\\\" \\\\u2014 with \\\\u00fcn\\\\u00efcode.\"\\n  },\\n  {\\n    \"name\": \"Crit B\",\\n    \"description\": \"Must evaluate on B\\'s data.\"\\n  }\\n]', 'doc_id': '200'}\n```"'''
)


# --- harness -----------------------------------------------------------------
_STUB_LITELLM = r"""
import json, os
from types import SimpleNamespace

_R = json.load(open(os.environ["PF_STUB_RESPONSES"], encoding="utf-8"))


async def acompletion(**kw):
    prompt = kw["messages"][0]["content"]
    with open(os.environ["PF_STUB_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": prompt,
                            "kwargs": {k: v for k, v in kw.items() if k != "messages"}}) + "\n")
    if _R.get("outage"):
        raise ConnectionError("judge outage")
    if prompt.startswith("previous_answer = "):
        content = _R["repair"]
    else:
        start = prompt.index("'doc_id': '") + len("'doc_id': '")
        content = _R["judge"][prompt[start:prompt.index("'", start)]]
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def completion(**kw):
    raise AssertionError("scorer must use acompletion")
"""


class Run:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        for d in ("app", "tests", "logs/verifier", "stub"):
            (tmp / d).mkdir(parents=True, exist_ok=True)
        src = pf.RUN_SCORER_PY
        for p in ("/app/answer.txt", "/tests/config.json", "/logs/verifier/reward.txt"):
            src = src.replace(f'"{p}"', repr(str(tmp) + p))
        (tmp / "tests" / "run_scorer.py").write_text(src, encoding="utf-8")
        (tmp / "stub" / "litellm.py").write_text(_STUB_LITELLM, encoding="utf-8")
        self.log = tmp / "llm_log.jsonl"
        self.reward_file = tmp / "logs" / "verifier" / "reward.txt"
        self.answer_file = tmp / "app" / "answer.txt"

    def __call__(self, cfg: dict, answer, responses: dict | None = None):
        (self.tmp / "tests" / "config.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )
        if answer is not None:
            data = answer if isinstance(answer, bytes) else answer.encode("utf-8")
            self.answer_file.write_bytes(data)
        (self.tmp / "responses.json").write_text(
            json.dumps(responses or {}), encoding="utf-8"
        )
        if self.reward_file.exists():  # test.sh deletes any stale reward
            self.reward_file.unlink()
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "OPENAI_API_KEY")
        }
        env.update(
            PYTHONPATH=str(self.tmp / "stub"),
            PF_STUB_RESPONSES=str(self.tmp / "responses.json"),
            PF_STUB_LOG=str(self.log),
        )
        proc = subprocess.run(
            [sys.executable, str(self.tmp / "tests" / "run_scorer.py")],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        reward = (
            float(self.reward_file.read_text().strip())
            if self.reward_file.exists()
            else None
        )
        return proc, reward

    def llm_calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [
            json.loads(line)
            for line in self.log.read_text(encoding="utf-8").splitlines()
        ]


def _cfg(case: dict) -> dict:
    qtype = case["query_id"].split("_")[0]
    return {
        "family": "litqa2-fulltext-search" if qtype == "litqa2" else "paper-finder",
        "query_id": case["query_id"],
        "query_type": qtype,
        "headline_metric": pf._headline_for(qtype),
        "gold_corpus_ids": case["gold"],
        "relevance_criteria": case.get("criteria", []),
        "total_relevant": case["total_relevant"],
    }


@pytest.mark.parametrize("name", sorted(CASES))
def test_matches_upstream(name: str, tmp_path: Path) -> None:
    case = CASES[name]
    run = Run(tmp_path)
    proc, reward = run(
        _cfg(case),
        case["answer"],
        {"judge": case.get("judge", {}), "repair": case.get("repair")},
    )
    expected = UPSTREAM[name]
    if expected == RAISE:
        assert proc.returncode != 0, proc.stderr
        assert reward is None, proc.stderr
    else:
        assert proc.returncode == 0, proc.stderr
        assert reward == pytest.approx(round(expected, 6), abs=1e-9), proc.stderr
    calls = run.llm_calls()
    got = sorted(hashlib.sha256(c["prompt"].encode("utf-8")).hexdigest() for c in calls)
    assert got == UPSTREAM_PROMPT_SHA256.get(name, []), [
        c["prompt"][:200] for c in calls
    ]
    for c in calls:
        # inspect_ai 0.3.203 effective request for get_model(haiku).generate(prompt)
        assert c["kwargs"]["model"] == "anthropic/claude-haiku-4-5"
        assert c["kwargs"]["max_tokens"] == 32000
        for k in ("temperature", "top_p", "top_k"):
            assert k not in c["kwargs"]


def test_judge_prompt_is_byte_identical(tmp_path: Path) -> None:
    case = CASES["semantic_judged"]
    run = Run(tmp_path)
    run(_cfg(case), case["answer"], {"judge": case["judge"]})
    prompts = [c["prompt"] for c in run.llm_calls()]
    assert UPSTREAM_PROMPT_DOC_200 in prompts


def test_semantic_oracle_nonce_short_circuits(tmp_path: Path) -> None:
    case = CASES["semantic_exact_gold_set"]
    cfg = dict(_cfg(case), oracle_marker="asta-bench-oracle/abc")
    payload = {
        "output": {
            "results": [dict(_res("100"), _oracle_marker="asta-bench-oracle/abc")]
        }
    }
    run = Run(tmp_path)
    proc, reward = run(cfg, json.dumps(payload))
    assert proc.returncode == 0 and reward == 1.0, proc.stderr
    assert run.llm_calls() == []
    # A wrong marker goes through the real formula (-> 0.0 for the gold set).
    payload["output"]["results"][0]["_oracle_marker"] = "asta-bench-oracle/forged"
    proc, reward = run(cfg, json.dumps(payload))
    assert proc.returncode == 0 and reward == 0.0, proc.stderr


def test_marker_ignored_for_specific_queries(tmp_path: Path) -> None:
    cfg = dict(_cfg(CASES["specific_mixed"]), oracle_marker="asta-bench-oracle/abc")
    payload = {
        "output": {
            "results": [dict(_res("999"), _oracle_marker="asta-bench-oracle/abc")]
        }
    }
    proc, reward = Run(tmp_path)(cfg, json.dumps(payload))
    assert proc.returncode == 0 and reward == 0.0, proc.stderr


def test_judge_outage_records_no_reward(tmp_path: Path) -> None:
    case = CASES["semantic_judged"]
    proc, reward = Run(tmp_path)(_cfg(case), case["answer"], {"outage": True})
    assert proc.returncode != 0 and reward is None, proc.stderr


def test_repair_outage_records_no_reward(tmp_path: Path) -> None:
    case = CASES["repair_ok"]
    proc, reward = Run(tmp_path)(_cfg(case), case["answer"], {"outage": True})
    assert proc.returncode != 0 and reward is None, proc.stderr


@pytest.mark.parametrize(
    "answer", [None, b"\xff\xfe\x00garbage\x80"], ids=["missing", "non-utf8"]
)
def test_unreadable_answer_scores_zero(answer, tmp_path: Path) -> None:
    proc, reward = Run(tmp_path)(_cfg(CASES["specific_mixed"]), answer)
    assert proc.returncode == 0 and reward == 0.0, proc.stderr


def test_missing_normalizer_is_verifier_error(tmp_path: Path) -> None:
    cfg = dict(_cfg(CASES["specific_mixed"]), total_relevant=None)
    proc, reward = Run(tmp_path)(cfg, CASES["specific_mixed"]["answer"])
    assert proc.returncode != 0 and reward is None


# --- builders: generated config / oracle / instruction -------------------------
def _write(builder_cls, record: SampleRecord, tmp: Path) -> Path:
    builder = builder_cls.__new__(builder_cls)  # no dataset / CLI state needed
    task_dir = tmp / "task"
    task_dir.mkdir(parents=True)
    builder.write_task(record, task_dir)
    return task_dir


def _oracle_answer(task_dir: Path) -> str:
    solve = (task_dir / "solution" / "solve.sh").read_text(encoding="utf-8")
    return (
        solve.split("<<'ORACLE_ANSWER_EOF'\n", 1)[1].rsplit("\nORACLE_ANSWER_EOF", 1)[0]
        + "\n"
    )


@pytest.mark.parametrize("qtype", ["semantic", "specific"])
def test_paper_finder_task_oracle_and_config(qtype: str, tmp_path: Path) -> None:
    qid = f"{qtype}_7"
    record = SampleRecord(
        sample_id=qid,
        split="test",
        instruction=" A query with spaces ",
        target=["10", "11"],
        metadata={
            "query_type": qtype,
            "relevance_criteria": CRIT if qtype == "semantic" else [],
            "total_relevant": 20 if qtype == "semantic" else 2,
        },
        workspace_files={"inspect_config.json": "{}"},
    )
    task_dir = _write(pf.PaperFinderBuilder, record, tmp_path)
    cfg = json.loads((task_dir / "tests" / "config.json").read_text())
    assert cfg["relevance_criteria"] == record.metadata["relevance_criteria"]
    assert cfg["gold_corpus_ids"] == ["10", "11"]
    assert ("oracle_marker" in cfg) == (qtype == "semantic")
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    assert instruction.startswith(
        pf.TASK_INSTRUCTIONS.format(query=" A query with spaces ")
    )
    assert "/app/answer.txt" in instruction
    assert "litellm==" in (task_dir / "environment" / "Dockerfile").read_text()
    toml = (task_dir / "task.toml").read_text()
    assert 'ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY:-}"' in toml

    proc, reward = Run(tmp_path / "run")(cfg, _oracle_answer(task_dir))
    assert proc.returncode == 0 and reward == 1.0, proc.stderr


def test_litqa2_search_task_oracle_goes_through_formula(tmp_path: Path) -> None:
    record = SampleRecord(
        sample_id="litqa2_6",
        split="test",
        instruction="Which gene?",
        target=["7", "8"],
        metadata={
            "query_type": "litqa2",
            "scorer_criteria": {"corpus_ids": ["7", "8"]},
            "total_relevant": 2,
            "lab_bench_id": "x",
        },
        workspace_files={"inspect_config.json": "{}"},
    )
    task_dir = _write(l2s.LitQA2FullTextSearchBuilder, record, tmp_path)
    cfg = json.loads((task_dir / "tests" / "config.json").read_text())
    assert "oracle_marker" not in cfg
    assert (
        'ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY:-}"'
        in (task_dir / "task.toml").read_text()
    )
    run = Run(tmp_path / "run")
    proc, reward = run(cfg, _oracle_answer(task_dir))
    assert proc.returncode == 0 and reward == 1.0, proc.stderr
    assert run.llm_calls() == []
