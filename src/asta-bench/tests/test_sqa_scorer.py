"""Offline equivalence tests for the sqa verifier (`sqa.RUN_SCORER_PY`).

The judge is a deterministic fake ``litellm``.  Every expected number / error
below was produced by running the real upstream scorers
(astabench/evals/sqa/task.py ``aggregate_scorer([score_sqa(simplified_eval,
assess_jointly), score_precision, score_citation(all_at_once)], 0.25 each)``,
smiky2011/asta-bench @ 17c84ca, inspect_ai 0.3.203, pydantic 2.13.3) with the
same fake judge plugged in as the Inspect model, and pasted in as literals.
The sha256 digests are of ``json.dumps([(role, text), ...])`` for every judge
request upstream made, so they pin the prompts byte-for-byte.

Needs pydantic (pinned in the verifier image); the no-citation fixture also
needs nltk + punkt_tab.  Run with e.g.
``uv run --with pytest --with pydantic==2.13.3 --with nltk==3.9.4 pytest tests/test_sqa_scorer.py``.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import sys
import types

import pytest

pytest.importorskip("pydantic")

from asta_bench.benchmarks import sqa as sqa_builder

# --- fixtures (identical to the ones fed to upstream) -----------------------
RUBRIC = {
    "case_id": "fixture-1",
    "question": "How do transformer models differ from recurrent neural networks?",
    "annotator": "fixture",
    "ingredients": [
        {
            "name": "answer_critical_0",
            "criterion": "Compare the architectures.",
            "weight": 0.5,
            "examples": [
                "parallel vs sequential processing",
                "self-attention vs recurrence",
            ],
        },
        {
            "name": "answer_critical_1",
            "criterion": "Discuss vanishing gradients.",
            "weight": 0.3,
            "examples": [],
        },
        {
            "name": "valuable_0",
            "criterion": "Mention a table comparison.",
            "weight": 0.2,
            "examples": ["a table"],
        },
        {"name": "no_criterion", "criterion": "", "weight": 0.1},
    ],
}

ANSWER_A = json.dumps(
    {
        "sections": [
            {
                "title": "Background",
                "text": "Transformers process tokens in parallel with self-attention [1]. RNNs process tokens sequentially [2].",
                "citations": [
                    {
                        "id": "[1]",
                        "snippets": ["The Transformer relies entirely on attention."],
                        "title": "Attention Is All You Need",
                    },
                    {
                        "id": "[2]",
                        "snippets": [],
                        "title": "Learning long-term dependencies is difficult",
                    },
                ],
            },
            {
                "title": "Training",
                "text": "RNNs suffer from vanishing gradients (Bengio 1994).\n\nPizza is a popular food in Italy (Smith 2020).",
                "citations": [
                    {
                        "id": "(Bengio 1994)",
                        "snippets": [
                            "Gradient descent struggles with long-term dependencies."
                        ],
                        "title": "Long-term dependencies",
                    },
                    {
                        "id": "(Smith 2020)",
                        "snippets": [
                            "Please click on the paper title to read the abstract on Semantic Scholar."
                        ],
                        "title": "Pizza",
                    },
                ],
                "table": {
                    "text": "| model | parallel |\n| Transformer | yes [1] |",
                    "citations": [
                        {
                            "id": "[1]",
                            "snippets": [
                                "The Transformer relies entirely on attention."
                            ],
                            "title": "Attention Is All You Need",
                        }
                    ],
                },
            },
        ]
    }
)

ANSWER_B = (
    "Here is my report:\n"
    + json.dumps(
        {
            "response": {
                "sections": [
                    {
                        "title": "Intro",
                        "text": "First sentence. Second sentence! Third one?",
                        "citations": [],
                    },
                    {
                        "text": "X uses attention [1].",
                        "citations": [
                            {
                                "id": "[1]",
                                "snippets": ["X uses attention"],
                                "title": "X",
                            }
                        ],
                    },
                ]
            }
        }
    )
    + "\nThanks."
)

ANSWER_C = json.dumps({"sections": []})

# Upstream results (global_avg is the reward).
UPSTREAM = {
    "A": {
        "ingredient_recall": 0.65,
        "answer_precision": 0.75,
        "citation_recall": 0.7,
        "citation_precision": 0.7,
        "f1": 0.7,
        "global_avg": 0.7,
    },
    "B": {
        "ingredient_recall": 1.0,
        "answer_precision": 1.0,
        "citation_recall": 0.125,
        "citation_precision": 0.5,
        "f1": 0.2,
        "global_avg": 0.65625,
    },
    "C": {
        "ingredient_recall": 0.0,
        "answer_precision": 1.0,
        "citation_recall": 0,
        "citation_precision": 0,
        "f1": 0,
        "global_avg": 0.25,
    },
}
# Upstream judge requests: kind -> sorted sha256 of the messages.
UPSTREAM_CALLS = {
    "A": {
        "citation": sorted(
            [
                "5f35429f39af5995010ec09b276a6026123b2b050109bdd6e4fab9862b0d068d",
                "82e8e2831cb73d3def569879f0075ffb92305c2d6f81ad19cbecce3cd18438a5",
                "c198f5a6833b9f4a79b064fd3e1e4fdf1f743334e7917dfe7c4d3828bce7fba8",
            ]
        ),
        "precision": [
            "af1a03f8b2bb2a7a0f04194741eb80b072ea8dc48a60841929bcf940ee6fffee"
        ],
        "rubric": ["309b062e9572b3137a65f7b2c7c0e7c9452c24744c715cdbba7f8d4afc5b2528"],
    },
    "B": {
        "citation": [
            "839447aad2b4afbea528754888498954932cacca6a906c04730137b83b8a2b2c"
        ],
        "precision": [
            "0844ce7596eb5e976d038149afad4c42d7e031a012e053ad90c4129115a1b657"
        ],
        "rubric": ["5b83a1f0b6728339b3333df6680e9dca341fe05674094237f6f15f40091935bb"],
    },
    "C": {
        "precision": [
            "743f8eb95364e8c0f3676f0fc1fb3516402fc673172222103d74cc17f7249525"
        ],
        "rubric": ["8bedb58431d5949f925970866afe4c481868f80c6177cf6316d681401935f219"],
    },
}


def fake_judge(kind: str, text: str) -> str:
    if kind == "rubric":
        if "<response></response>" in text:
            s = [0, 0, 0]
        elif "X uses attention" in text:
            s = [2, 2, 2]
        else:
            s = [2, 1, 0]
        return "Sure:\n" + json.dumps(
            {
                "scores": [
                    {
                        "criteria_idx": i + 1,
                        "reasoning": "r",
                        "score": v,
                        "evidence": "e",
                    }
                    for i, v in enumerate(s)
                ]
            }
        )
    if kind == "precision":
        if "Pizza is a popular food" in text:
            return json.dumps(
                {
                    "irrelevant_paragraphs": [
                        {
                            "reason": "off-topic",
                            "answer_text": "Pizza is a popular food in Italy (Smith 2020).",
                        }
                    ]
                }
            )
        return json.dumps({"irrelevant_paragraphs": []})
    body = text.split("\n\nText:\n", 1)[1]
    if body.startswith("Transformers process"):
        claims = [
            {
                "text": "Transformers parallel",
                "supporting": ["[1]"],
                "non_supporting": [],
                "is_fully_supported": True,
            },
            {
                "text": "RNNs sequential",
                "supporting": ["[2]"],
                "non_supporting": [],
                "is_fully_supported": True,
            },
        ]
    elif body.startswith("RNNs suffer"):
        claims = [
            {
                "text": "vanishing",
                "supporting": ["(Bengio 1994)"],
                "non_supporting": [],
                "is_fully_supported": True,
            },
            {
                "text": "pizza",
                "supporting": [],
                "non_supporting": ["(Smith 2020)"],
                "is_fully_supported": False,
            },
        ]
    elif body.startswith("| model"):
        claims = [
            {
                "text": "table",
                "supporting": ["[1]", 5],
                "non_supporting": [],
                "is_fully_supported": "true",
            }
        ]
    elif body.startswith("X uses attention"):
        claims = [{"text": "X", "supporting": ["1"], "is_fully_supported": True}]
    else:
        raise AssertionError(body[:80])
    return json.dumps({"claims": claims})


def classify(msgs) -> str:
    if msgs[0][0] == "system":
        return "rubric"
    t = msgs[-1][1]
    if t.startswith("You are given a query and a corresponding long answer."):
        return "precision"
    if t.startswith("You are a claim validator."):
        return "citation"
    raise AssertionError(t[:80])


class FakeLitellm(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("litellm")
        self.calls: list[dict] = []
        self.judge = fake_judge
        self.api_error: Exception | None = None

    async def acompletion(self, **kwargs):
        msgs = [(m["role"], m["content"]) for m in kwargs["messages"]]
        kind = classify(msgs)
        self.calls.append(
            {
                "kind": kind,
                "kwargs": kwargs,
                "sha": hashlib.sha256(json.dumps(msgs).encode()).hexdigest(),
            }
        )
        if self.api_error is not None:
            raise self.api_error
        content = self.judge(kind, msgs[-1][1])
        msg = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    def kinds(self, kind: str) -> list[dict]:
        return [c for c in self.calls if c["kind"] == kind]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SQA_JUDGE_RETRY_BASE_DELAY", "0")
    for k in (
        "JUDGE_MODEL",
        "SQA_JUDGE_STRUCTURED_OUTPUT",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    fake = FakeLitellm()
    monkeypatch.setitem(sys.modules, "litellm", fake)
    path = tmp_path / "run_scorer.py"
    path.write_text(sqa_builder.RUN_SCORER_PY)
    spec = importlib.util.spec_from_file_location("sqa_run_scorer_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ANSWER_FILE = tmp_path / "answer.txt"
    mod.CONFIG_FILE = tmp_path / "config.json"
    mod.REWARD_FILE = tmp_path / "reward.txt"
    mod.CONFIG_FILE.write_text(
        json.dumps(
            {"oracle_marker": "asta-bench-oracle/nonce", "rubric_payload": RUBRIC}
        )
    )
    return types.SimpleNamespace(mod=mod, fake=fake, tmp=tmp_path)


def _score(env, answer: str) -> dict:
    return asyncio.run(env.mod.score_all(answer, RUBRIC))


def _main(env, answer: str):
    env.mod.ANSWER_FILE.write_text(answer)
    if env.mod.REWARD_FILE.exists():
        env.mod.REWARD_FILE.unlink()
    rc = env.mod.main()
    return rc, float(env.mod.REWARD_FILE.read_text())


def _check_calls(env, key: str) -> None:
    got: dict[str, list[str]] = {}
    for c in env.fake.calls:
        got.setdefault(c["kind"], []).append(c["sha"])
    assert {k: sorted(v) for k, v in got.items()} == UPSTREAM_CALLS[key]


def _need_punkt():
    nltk = pytest.importorskip("nltk")
    try:
        nltk.data.find("tokenizers/punkt_tab/english/")
    except LookupError:
        pytest.skip("nltk punkt_tab data not installed")


# --- (a) mocked judge -> same numbers as upstream ---------------------------
def test_fixture_a_matches_upstream(env):
    assert _score(env, ANSWER_A) == pytest.approx(UPSTREAM["A"], abs=1e-12)
    _check_calls(env, "A")
    env.fake.calls.clear()
    assert _main(env, ANSWER_A) == (0, pytest.approx(0.7, abs=1e-6))


def test_fixture_b_no_citation_section_and_response_wrapper(env):
    _need_punkt()
    assert _score(env, ANSWER_B) == pytest.approx(UPSTREAM["B"], abs=1e-12)
    _check_calls(env, "B")


def test_empty_sections_list_still_runs_rubric_and_precision(env):
    # upstream gates on `.get("sections") is None`, so [] is judged.
    assert _score(env, ANSWER_C) == pytest.approx(UPSTREAM["C"], abs=1e-12)
    _check_calls(env, "C")


def test_judge_request_parameters(env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://proxy.example:3000")
    _score(env, ANSWER_A)
    names = {
        "rubric": "response_criteria_scores",
        "precision": "answer_precision",
        "citation": "assess_citation_group",
    }
    schemas = {
        "rubric": env.mod.RESPONSE_CRITERIA_SCORES_SCHEMA[1],
        "precision": env.mod.ANSWER_PRECISION_SCHEMA[1],
        "citation": env.mod.ASSESS_CITATION_GROUP_SCHEMA[1],
    }
    for c in env.fake.calls:
        kw = c["kwargs"]
        assert kw["model"] == "anthropic/claude-haiku-4-5"
        assert kw["temperature"] == 0.5
        assert kw["max_tokens"] == 32000
        assert kw["api_base"] == "http://proxy.example:3000"
        assert "num_retries" not in kw  # retries: _judge_with_backoff
        assert kw["output_format"] == {
            "type": "json_schema",
            "schema": schemas[c["kind"]],
        }
        assert kw["extra_headers"] == {
            "anthropic-beta": "structured-outputs-2025-11-13"
        }
        if c["kind"] == "precision":
            assert "top_p" not in kw
        else:
            assert kw["top_p"] == 0.95
    assert set(names) == {c["kind"] for c in env.fake.calls}
    # spot-check the schema literal against upstream's required fields
    assert schemas["rubric"]["properties"]["scores"]["items"]["required"] == [
        "criteria_idx",
        "reasoning",
        "score",
        "evidence",
    ]


def test_structured_output_can_be_disabled(env, monkeypatch):
    monkeypatch.setenv("SQA_JUDGE_STRUCTURED_OUTPUT", "0")
    assert _score(env, ANSWER_A) == pytest.approx(UPSTREAM["A"], abs=1e-12)
    for c in env.fake.calls:
        assert "output_format" not in c["kwargs"] and "extra_headers" not in c["kwargs"]


# --- answers upstream scores as 0 (no judge call) ----------------------------
@pytest.mark.parametrize("answer", ["{}", "no json here", "", "[1, 2, 3]"])
def test_unparsable_answer_scores_zero_without_judge(env, answer):
    assert _main(env, answer) == (0, 0.0)
    assert env.fake.calls == []


def test_oracle_nonce(env):
    assert _main(
        env, json.dumps({"_oracle_marker": "asta-bench-oracle/nonce", "sections": []})
    ) == (0, 1.0)
    assert env.fake.calls == []


# --- (b) malformed answers: upstream raises -> no reward ---------------------
# pydantic.ValidationError and json.JSONDecodeError are ValueErrors.
UPSTREAM_ERRORS = (ValueError, KeyError, TypeError, AttributeError)
_BASE = json.loads(ANSWER_A)


def _mut(f):
    d = copy.deepcopy(_BASE)
    f(d)
    return json.dumps(d)


# Each of these raised in upstream (ValidationError / KeyError / TypeError /
# AttributeError -> Inspect sample error).
MALFORMED = {
    "snippets_str": _mut(
        lambda d: d["sections"][0]["citations"][0].__setitem__("snippets", "a string")
    ),
    "cit_id_missing": _mut(lambda d: d["sections"][0]["citations"][0].pop("id")),
    "cit_id_int": _mut(lambda d: d["sections"][0]["citations"][0].__setitem__("id", 1)),
    "text_null": _mut(lambda d: d["sections"][0].__setitem__("text", None)),
    "text_missing": _mut(lambda d: d["sections"][0].pop("text")),
    "citations_missing": _mut(lambda d: d["sections"][0].pop("citations")),
    "title_missing_on_title_only_citation": _mut(
        lambda d: d["sections"][0]["citations"][1].pop("title")
    ),
    "sections_null": json.dumps({"sections": None}),
    "no_sections_key": json.dumps({"foo": 1}),
    "sections_dict": json.dumps({"sections": {"a": 1}}),
    "bare_int_in_braces": "{5}",
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_malformed_answer_raises_without_reward(env, name):
    env.mod.ANSWER_FILE.write_text(MALFORMED[name])
    with pytest.raises(UPSTREAM_ERRORS):
        env.mod.main()
    assert not env.mod.REWARD_FILE.exists()
    assert env.fake.calls == []  # fails before any judge call


# --- (b) judge outputs: upstream pydantic validation + 21-attempt retry ------
def _bad(kind_target, payload):
    def j(kind, text):
        return payload if kind == kind_target else fake_judge(kind, text)

    return j


def _scores(score, idxs=(1, 2, 3), **extra):
    return json.dumps(
        {
            "scores": [
                dict(
                    {
                        "criteria_idx": i,
                        "reasoning": "r",
                        "score": score,
                        "evidence": "e",
                    },
                    **extra,
                )
                for i in idxs
            ]
        }
    )


# name -> (judge kind, output, upstream attempts) ; all raised upstream.
INVALID_JUDGE = {
    "rubric_score3": ("rubric", _scores(3), 21),
    "rubric_score1.5": ("rubric", _scores(1.5), 21),
    "rubric_score_str2": ("rubric", _scores("2"), 21),
    "rubric_no_reasoning": (
        "rubric",
        json.dumps(
            {
                "scores": [
                    {"criteria_idx": i, "score": 2, "evidence": "e"} for i in (1, 2, 3)
                ]
            }
        ),
        21,
    ),
    "rubric_missing_criterion": ("rubric", _scores(2, idxs=(1, 2)), 21),
    "rubric_no_json": ("rubric", "I cannot help", 21),
    "citation_supporting_null": (
        "citation",
        json.dumps(
            {"claims": [{"text": "t", "supporting": None, "is_fully_supported": True}]}
        ),
        21,
    ),
    "citation_supporting_str": (
        "citation",
        json.dumps(
            {"claims": [{"text": "t", "supporting": "[1]", "is_fully_supported": True}]}
        ),
        21,
    ),
    "citation_no_text": (
        "citation",
        json.dumps({"claims": [{"supporting": ["[1]"], "is_fully_supported": True}]}),
        21,
    ),
    # precision has no desired_schema upstream: parsed once, then KeyError /
    # AttributeError outside the retry loop.
    "precision_missing_key": ("precision", json.dumps({"irrelevant": []}), 1),
    "precision_text_not_str": (
        "precision",
        json.dumps({"irrelevant_paragraphs": [{"reason": "r", "answer_text": 5}]}),
        1,
    ),
}


@pytest.mark.parametrize("name", sorted(INVALID_JUDGE))
def test_invalid_judge_output_raises_after_upstream_retries(env, name):
    kind, payload, attempts = INVALID_JUDGE[name]
    env.fake.judge = _bad(kind, payload)
    env.mod.ANSWER_FILE.write_text(ANSWER_A)
    with pytest.raises(UPSTREAM_ERRORS):
        env.mod.main()
    assert not env.mod.REWARD_FILE.exists()
    # citation groups run sequentially, so the first group exhausts retries.
    assert len(env.fake.kinds(kind)) == attempts


def test_criteria_idx_string_is_coerced_like_upstream(env):
    env.fake.judge = _bad("rubric", _scores(2, idxs=("1", "2", "3")))
    got = _score(env, ANSWER_A)
    assert got["global_avg"] == pytest.approx(0.7875000000000001, abs=1e-12)
    assert got["ingredient_recall"] == 1.0


def test_is_fully_supported_false_string_is_false(env):
    # pydantic lax bool: "false" -> False (the old port's bool("false") was True)
    env.fake.judge = _bad(
        "citation",
        json.dumps(
            {
                "claims": [
                    {"text": "t", "supporting": ["[1]"], "is_fully_supported": "false"}
                ]
            }
        ),
    )
    got = _score(env, ANSWER_A)
    assert got == pytest.approx(
        {
            "ingredient_recall": 0.65,
            "answer_precision": 0.75,
            "citation_recall": 0.0,
            "citation_precision": 1.0,
            "f1": 0.0,
            "global_avg": 0.6,
        },
        abs=1e-12,
    )


def test_invalid_then_valid_judge_output_recovers(env):
    first = {"n": 0}

    def j(kind, text):
        if kind == "rubric" and first["n"] == 0:
            first["n"] += 1
            return _scores(3)
        return fake_judge(kind, text)

    env.fake.judge = j
    assert _score(env, ANSWER_A) == pytest.approx(UPSTREAM["A"], abs=1e-12)
    assert len(env.fake.kinds("rubric")) == 2


def test_api_error_raises_immediately(env):
    env.fake.api_error = RuntimeError("judge outage")
    env.mod.ANSWER_FILE.write_text(ANSWER_A)
    with pytest.raises(RuntimeError):
        env.mod.main()
    assert not env.mod.REWARD_FILE.exists()
    # one call per concurrently-started judge, no parse-retry loop
    assert len(env.fake.calls) <= 3


def test_broken_config_raises(env):
    env.mod.CONFIG_FILE.write_text(json.dumps({"oracle_marker": "x"}))
    env.mod.ANSWER_FILE.write_text(ANSWER_A)
    with pytest.raises(KeyError):
        env.mod.main()
    assert not env.mod.REWARD_FILE.exists()


def test_dockerfile_pins_verifier_deps():
    df = sqa_builder.DOCKERFILE
    for pin in (
        '"litellm==1.82.3"',
        '"pydantic==2.13.3"',
        '"nltk==3.9.4"',
        "punkt_tab",
    ):
        assert pin in df
    assert "COPY tests" not in df


def test_generated_scorer_compiles():
    compile(sqa_builder.RUN_SCORER_PY, "run_scorer.py", "exec")
