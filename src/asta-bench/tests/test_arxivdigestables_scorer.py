"""Offline fidelity tests for the arxivdigestables-clean verifier.

Every expected value below was computed with the REAL upstream code
(astabench/evals/arxivdigestables, fork commit 17c84ca, inspect_ai 0.3.203,
pydantic 2.13.3, pandas 3.0.2, tabulate 0.10.0) in the upstream venv: the
upstream `score_tables` scorer was run with `Model.generate` patched to return
the same canned unroller/judge responses used here, recording the sha256 of
every prompt it sent.  Nothing here needs the upstream checkout at run time.

The judge-path tests need pydantic + tabulate (present in the task image, not
in the adapter venv); run them with
`uv run --with pytest --with pydantic --with tabulate pytest tests/test_arxivdigestables_scorer.py`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from asta_bench.benchmarks import arxivdigestables as adt

# --- Upstream fixtures --------------------------------------------------------

UPSTREAM_SHA256 = {
    # prompts.py constants
    "INPUT_PROMPT": "afa1e00d7743252fb5e614bb0105338cf193cd61974be06703eef7794331fbcd",
    "UNROLL_PROMPT": "68c4ae8d0008e3f1b82c88b1cccc18653a532bdd73ea0a90d7f379f3e4c30c8c",
    "EVAL_PROMPT": "91fd14a9a2e4e2f9998d68f121aeb6f014e0d4e5aa0ad023fffc2df41f4c6f3e",
    # json.dumps(Table.schema(), indent=2)
    "TABLE_SCHEMA_JSON": "d66758ca0029ea197f2481fa288fa6766b9a1bd57a6e393d2c5a90b88b55fbbc",
}

UNROLLED = (
    "1. Paper 11 uses method A.\n2. Paper 22 uses method B.\n"
    "3. Paper 11 reports 90% accuracy."
)
UNROLLER_RESPONSE = UNROLLED + "\n\n"
JUDGE_RESPONSES = ["True", "false", "Unknown", "It is untrue.", "TRUE."]
GOLD = (
    "Paper 11 uses method A.\n\nPaper 22 uses method B.\n   \n"
    "Paper 11 reports accuracy of 90%.\nPaper 22 reports accuracy of 80%.\n"
    "Paper 11 is about [STATEMENT] tokens.\n"
)
MAIN_ANSWER = (
    "Here is my table:\n```json\n"
    '{"cell_values": [{"paper_id": "11", "column_name": "Method", "cell_value": "A"}, '
    '{"paper_id": "22", "column_name": "Method", "cell_value": "B"}, '
    '{"paper_id": "11", "column_name": "Accuracy", "cell_value": "90%"}], "notes": 1}'
    "\n```\nDone."
)
JUDGE_PROMPT_SHA = [
    "f15641d034ce76f766652fcd5ebc426c1b016190e816e7183ca559641b61489e",
    "f68ed7e52fcb4ac5e31883a53a176062f03bfadadd0150478796b66649a30053",
    "dadc1b734628b11edd1f3e093c7b11d35956f622b58320848d0db5a8219e6ff8",
    "6fe3f79c8b78c4cb1d2954daf8edc59034582545d4db31563813d0a1d7b69c4b",
    "6ee4eecfeca529cf618e0c10b2c0b8586681759a105420b57a985f5fe21947c4",
]
UPSTREAM_SCORED = {
    # name: (answer, recall, prompt sha256s in call order)
    "main": (
        MAIN_ANSWER,
        0.6,
        ["609ea86f256d94e3e12ebfb9075e3f4e2656b09601680489553cfd9d83c22482"]
        + JUDGE_PROMPT_SHA,
    ),
    "empty_list": (
        '{"cell_values": []}',
        0.6,
        ["a3c60abe365ed36a8e550a594104d5a4db8d331f2af0c6940da73d8d39a9f94f"]
        + JUDGE_PROMPT_SHA,
    ),
}

# Answers upstream scores 0 without any model call (pydantic lax mode does
# not coerce numbers/bools/null to str; missing keys and non-list
# cell_values are rejected; no `{...}` slice; invalid JSON).
UPSTREAM_ZERO = {
    "int_paper_id": '{"cell_values":[{"paper_id":1,"column_name":"a","cell_value":"x"}]}',
    "float_cell": '{"cell_values":[{"paper_id":"1","column_name":"a","cell_value":1.5}]}',
    "bool_cell": '{"cell_values":[{"paper_id":"1","column_name":"a","cell_value":true}]}',
    "null_cell": '{"cell_values":[{"paper_id":"1","column_name":"a","cell_value":null}]}',
    "list_cell": '{"cell_values":[{"paper_id":"1","column_name":"a","cell_value":["x"]}]}',
    "missing_key": '{"cell_values":[{"paper_id":"1","column_name":"a"}]}',
    "no_cell_values": "{}",
    "cell_values_null": '{"cell_values":null}',
    "cell_values_dict": '{"cell_values":{"0":{"paper_id":"1","column_name":"a","cell_value":"x"}}}',
    "no_braces": "no json here",
    "invalid_json": '{"cell_values": [}',
    "deep_braces": "{" * 5000,
}


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# --- Prompt / instruction fidelity ---------------------------------------------


@pytest.mark.parametrize("name", sorted(UPSTREAM_SHA256))
def test_prompt_constants_byte_identical(name: str) -> None:
    assert _sha(getattr(adt, name)) == UPSTREAM_SHA256[name]


def test_rendered_scorer_embeds_identical_prompts(tmp_path: Path) -> None:
    mod = _load_scorer(tmp_path)
    assert _sha(mod.UNROLL_PROMPT) == UPSTREAM_SHA256["UNROLL_PROMPT"]
    assert _sha(mod.EVAL_PROMPT) == UPSTREAM_SHA256["EVAL_PROMPT"]


def test_paper_list_matches_upstream_abstract_handling() -> None:
    papers = [
        {"corpus_id": 1, "title": "T1", "abstract": "  Abs.  "},
        {"corpus_id": 2, "title": "T2", "abstract": "   "},
        {"corpus_id": 3, "title": "T3", "abstract": None},
        {"corpus_id": 4, "title": "T4"},
    ]
    assert adt._make_paper_list_input(papers) == (
        "Paper 1 title: T1\nPaper 1 abstract: Abs.\n\n"
        "Paper 2 title: T2\nPaper 2 abstract: \n\n"
        "Paper 3 title: T3\nPaper 3 abstract: None\n\n"
        "Paper 4 title: T4\nPaper 4 abstract: None\n\n"
    )


def test_instruction_is_upstream_input_plus_submit_section() -> None:
    instance = {
        "caption": "Cap [COL_NUM]",
        "table": {"c1": {"1": "a", "2": "b"}, "c2": {"1": "x", "2": "y"}},
        "row_bib_map": [
            {"corpus_id": 1, "title": "T1", "abstract": "A1"},
            {"corpus_id": 2, "title": "T2", "abstract": "A2"},
        ],
    }
    instr = adt._build_instruction(instance)
    assert instr.endswith(adt.SUBMIT_SECTION)
    upstream = instr[: -len(adt.SUBMIT_SECTION)]
    # Upstream substitutes COL_NUM/PAPER_NUM before CAPTION.
    assert "Cap [COL_NUM]" in upstream
    assert upstream.endswith(
        "\n\nRespond with the following json schema:\n" + adt.TABLE_SCHEMA_JSON
    )


# --- Scorer behaviour (mocked judge) -------------------------------------------


def _load_scorer(tmp_path: Path, calls: list[str] | None = None, responses=None):
    src = tmp_path / "run_scorer.py"
    src.write_text(adt._render_run_scorer())
    if calls is not None:
        fake = types.ModuleType("litellm")
        fake.drop_params = False

        def completion(**kw):
            assert kw["temperature"] == 0.0
            assert kw["max_tokens"] == 32000
            assert "num_retries" not in kw  # retries: _judge_with_backoff
            assert len(kw["messages"]) == 1 and kw["messages"][0]["role"] == "user"
            calls.append(kw["messages"][0]["content"])
            text = responses[len(calls) - 1]
            msg = types.SimpleNamespace(content=text)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

        fake.completion = completion
        sys.modules["litellm"] = fake
    spec = importlib.util.spec_from_file_location(f"adt_scorer_{id(src)}", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ANSWER_FILE = tmp_path / "answer.txt"
    mod.CONFIG_FILE = tmp_path / "config.json"
    mod.REWARD_FILE = tmp_path / "reward.txt"
    return mod


@pytest.fixture(autouse=True)
def _restore_litellm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    saved = sys.modules.get("litellm")
    yield
    if saved is None:
        sys.modules.pop("litellm", None)
    else:
        sys.modules["litellm"] = saved


def _run(tmp_path, answer, gold=GOLD, marker="asta-bench-oracle/abc", responses=None):
    calls: list[str] = []
    mod = _load_scorer(
        tmp_path, calls, responses or [UNROLLER_RESPONSE, *JUDGE_RESPONSES]
    )
    (tmp_path / "answer.txt").write_text(answer)
    (tmp_path / "config.json").write_text(
        json.dumps({"gold_unrolled": gold, "oracle_marker": marker})
    )
    rc = mod.main()
    reward = float((tmp_path / "reward.txt").read_text())
    return rc, reward, calls


def _need_judge_deps():
    pytest.importorskip("pydantic")
    pytest.importorskip("tabulate")


@pytest.mark.parametrize("name", sorted(UPSTREAM_SCORED))
def test_recall_matches_upstream(tmp_path: Path, name: str) -> None:
    _need_judge_deps()
    answer, recall, prompt_shas = UPSTREAM_SCORED[name]
    rc, reward, calls = _run(tmp_path, answer)
    assert rc == 0
    assert reward == pytest.approx(recall)
    assert [_sha(c) for c in calls] == prompt_shas


@pytest.mark.parametrize("name", sorted(UPSTREAM_ZERO))
def test_schema_rejections_score_zero_without_judge(tmp_path: Path, name: str) -> None:
    _need_judge_deps()
    rc, reward, calls = _run(tmp_path, UPSTREAM_ZERO[name])
    assert (rc, reward, calls) == (0, 0.0, [])


def test_gold_equal_answer_is_judged_not_short_circuited(tmp_path: Path) -> None:
    _need_judge_deps()
    cells = [{"paper_id": "11", "column_name": "Method", "cell_value": "A"}]
    answer = json.dumps({"cell_values": cells})
    rc, reward, calls = _run(
        tmp_path, answer, gold="s1\ns2\n", responses=[UNROLLER_RESPONSE, "true", "no"]
    )
    assert (rc, reward, len(calls)) == (0, 0.5, 3)


def test_forged_marker_is_judged(tmp_path: Path) -> None:
    _need_judge_deps()
    answer = json.dumps(
        {"_oracle_marker": "asta-bench-oracle/guess", "cell_values": []}
    )
    rc, reward, calls = _run(
        tmp_path, answer, gold="s1\n", responses=[UNROLLER_RESPONSE, "false"]
    )
    assert (rc, reward, len(calls)) == (0, 0.0, 2)


def test_oracle_marker_short_circuits(tmp_path: Path) -> None:
    gold_cells = [{"paper_id": "1", "column_name": "c", "cell_value": "v"}]
    payload = adt._build_oracle_payload(gold_cells, "asta-bench-oracle/xyz")
    rc, reward, calls = _run(
        tmp_path, json.dumps(payload, indent=2), marker="asta-bench-oracle/xyz"
    )
    assert (rc, reward, calls) == (0, 1.0, [])


def test_empty_gold_raises_like_upstream(tmp_path: Path) -> None:
    _need_judge_deps()
    with pytest.raises(ZeroDivisionError):
        _run(tmp_path, MAIN_ANSWER, gold="\n   \n", responses=[UNROLLER_RESPONSE])


def test_judge_failure_propagates(tmp_path: Path) -> None:
    _need_judge_deps()
    with pytest.raises(IndexError):
        # Responses run out on the 2nd judge call -> exception, no reward.
        _run(tmp_path, MAIN_ANSWER, responses=[UNROLLER_RESPONSE, "true"])
    assert not (tmp_path / "reward.txt").exists()
