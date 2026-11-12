"""Unit tests for the CharXiv adapter.

Tests that compare against the upstream CharXiv code need a local checkout of
princeton-nlp/CharXiv@7ebe88f; point CHARXIV_UPSTREAM_DIR at it (they are
skipped otherwise).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest

from charxiv import adapter as A

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_TESTS = ROOT / "src" / "charxiv" / "task-template" / "tests"
UPSTREAM = Path(os.environ.get("CHARXIV_UPSTREAM_DIR", "/nonexistent"))
needs_upstream = pytest.mark.skipif(
    not (UPSTREAM / "src" / "constants.py").exists(), reason="CHARXIV_UPSTREAM_DIR not set"
)


def load_judge():
    tests_dir = TEMPLATE_TESTS
    # judge.py imports charxiv_constants from its own directory
    sys.modules["charxiv_constants"] = A.C
    spec = importlib.util.spec_from_file_location("charxiv_judge", tests_dir / "judge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- fixtures

DESC = {
    "0": {"figure_id": 0, "num_subplots": 2, "subplot_loc": [1, 2], "qids": [7, 13, 11, 18],
          "answers": ["60", "A, B", "Yes", "1 by 2"]},
    "5": {"figure_id": 5, "num_subplots": 1, "subplot_loc": "the left plot", "qids": [1, 2, 3, 19],
          "answers": ["Not Applicable", "x", "y", "1"]},
}
REAS = {
    "0": {"figure_id": 0, "query": "Which model declines more?", "answer": "Joint-CNN",
          "inst_category": 1, "qa_source": 1},
    "5": {"figure_id": 5, "query": "What is the gap?", "answer": "0.25",
          "inst_category": 4, "qa_source": 2},
}
META = {k: {"category": "cs", "year": "20", "paper_id": "2004.10956"} for k in DESC}


@pytest.fixture
def source_dir(tmp_path):
    d = tmp_path / "src"
    (d / "data").mkdir(parents=True)
    (d / "images").mkdir()
    (d / "data" / "descriptive_val.json").write_text(json.dumps(DESC))
    (d / "data" / "reasoning_val.json").write_text(json.dumps(REAS))
    (d / "data" / "image_metadata_val.json").write_text(json.dumps(META))
    for k in DESC:
        (d / "images" / f"{k}.jpg").write_bytes(b"\xff\xd8fakejpeg" + k.encode())
    return d


# ---------------------------------------------------------------- adapter


def test_task_ids_and_order(source_dir):
    tasks = A.load_tasks(A.CharXivSource(source_dir=source_dir))
    ids = [t.task_id for t in tasks]
    assert ids == [
        "charxiv-descriptive-0-0", "charxiv-descriptive-0-1", "charxiv-descriptive-0-2",
        "charxiv-descriptive-0-3", "charxiv-reasoning-0",
        "charxiv-descriptive-5-0", "charxiv-descriptive-5-1", "charxiv-descriptive-5-2",
        "charxiv-descriptive-5-3", "charxiv-reasoning-5",
    ]
    assert len(set(ids)) == len(ids)


def test_question_construction(source_dir):
    tasks = {t.task_id: t for t in A.load_tasks(A.CharXivSource(source_dir=source_dir))}
    assert tasks["charxiv-descriptive-0-0"].question.startswith(
        "For the subplot at row 1 and column 2, what is the spatially highest"
    )
    assert tasks["charxiv-descriptive-0-3"].question.startswith("What is the layout")
    assert tasks["charxiv-descriptive-5-0"].question.startswith("For the left plot, what is its title?")
    assert "must be a number with 2 decimal places" in tasks["charxiv-reasoning-5"].question


def test_generate_task_dirs(source_dir, tmp_path):
    out = tmp_path / "out"
    paths = A.CharXivAdapter(output_dir=out, source_dir=source_dir).run()
    assert len(paths) == 10
    t = out / "charxiv-reasoning-5"
    cfg = tomllib.loads((t / "task.toml").read_text())
    assert cfg["version"] == "1.0"
    assert cfg["task"]["name"] == "princeton-nlp/charxiv-reasoning-5"
    assert cfg["task"]["authors"][0]["name"] == "Zirui Wang"
    assert "OPENAI_API_KEY" in cfg["verifier"]["env"]
    instr = (t / "instruction.md").read_text()
    assert "/app/images/5.jpg" in instr and "/app/answer.txt" in instr
    assert "0.25" not in instr.replace("2 decimal", "")  # no answer leak
    assert (t / "environment" / "images" / "5.jpg").exists()
    assert "COPY images/5.jpg /app/images/5.jpg" in (t / "environment" / "Dockerfile").read_text()
    assert "0.25" in (t / "solution" / "solve.sh").read_text()
    assert json.loads((t / "tests" / "config.json").read_text())["ground_truth"] == "0.25"
    assert (t / "tests" / "charxiv_constants.py").exists()
    for p in out.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".toml", ".sh"} or p.name == "Dockerfile":
            assert "{{" not in p.read_text(), p
    # no answers anywhere in the agent-visible environment
    env_text = (t / "environment" / "Dockerfile").read_text()
    assert "0.25" not in env_text


def test_limit_overwrite_taskids(source_dir, tmp_path):
    out = tmp_path / "out"
    assert len(A.CharXivAdapter(output_dir=out, source_dir=source_dir, limit=3).run()) == 3
    with pytest.raises(FileExistsError):
        A.CharXivAdapter(output_dir=out, source_dir=source_dir, limit=1).run()
    A.CharXivAdapter(output_dir=out, source_dir=source_dir, limit=1, overwrite=True).run()
    p = A.CharXivAdapter(output_dir=tmp_path / "o2", source_dir=source_dir,
                         task_ids=["charxiv-reasoning-0"]).run()
    assert [x.name for x in p] == ["charxiv-reasoning-0"]
    p = A.CharXivAdapter(output_dir=tmp_path / "o3", source_dir=source_dir,
                         modes=("reasoning",)).run()
    assert len(p) == 2


# ---------------------------------------------------------------- judge


def test_judge_shortcuts():
    J = load_judge()
    cfg = {"mode": "reasoning", "inst_category": 1, "raw_question": "q", "ground_truth": "Joint-CNN"}
    def boom(*a):
        raise AssertionError("judge must not be called")
    assert J.grade(cfg, "Joint-CNN", chat_fn=boom)["score"] == 1
    assert J.grade(cfg, "", chat_fn=boom)["score"] == 0
    r = J.grade(cfg, "Joint-CNN", chat_fn=lambda p, m: '{"extracted_answer": "Joint-CNN", "score": 1}',
                shortcut=False)
    assert r["method"] == "llm_judge" and r["score"] == 1


def test_judge_retry_semantics():
    J = load_judge()
    cfg = {"mode": "descriptive", "qid": 11, "ground_truth": "Yes"}
    calls = []
    def bad(p, m):
        calls.append(m)
        return '{"foo": 1}'
    r = J.grade(cfg, "No", chat_fn=bad)
    assert r["score"] == 0 and r["invalid"] and len(calls) == 10
    def down(p, m):
        raise ConnectionError("unreachable")
    with pytest.raises(J.NoJudgeResponse):
        J.grade(cfg, "No", chat_fn=down)
    r = J.grade(cfg, "No", chat_fn=lambda p, m: '{"extract_answer_T1": "No", "score_T1": 0}')
    assert r["score"] == 0 and not r["invalid"]


# ---------------------------------------------------------------- upstream equivalence


@needs_upstream
def test_vendored_constants_identical():
    up = (UPSTREAM / "src" / "constants.py").read_text()
    ours = (ROOT / "src" / "charxiv" / "upstream_constants.py").read_text()
    assert ours.endswith(up)


@needs_upstream
def test_matches_upstream_query_and_grading_builders():
    sys.path.insert(0, str(UPSTREAM / "src"))
    try:
        import descriptive_utils as DU
        import reasoning_utils as RU
    finally:
        sys.path.pop(0)
    data_d = json.loads((UPSTREAM / "data" / "descriptive_val.json").read_text())
    data_r = json.loads((UPSTREAM / "data" / "reasoning_val.json").read_text())
    up_d = DU.build_descriptive_quries(data_d, "images")
    up_r = RU.build_reasoning_queries(data_r, "images")
    src = A.CharXivSource(source_dir=UPSTREAM)
    tasks = A.load_tasks(src)
    assert len(tasks) == 5000
    J = load_judge()
    for t in tasks:
        if t.mode == "descriptive":
            assert t.question == up_d[f"{t.figure_id}_{t.subq_idx}"]["question"]
            key = f"{t.figure_id}_{t.subq_idx}"
            groups = {i: [] for i in range(1, 20)}
            groups[t.qid].append((key, "RESP", t.answer))
            up_q = DU.build_descriptive_grading_queries(groups, nq_per_query=5)[0]["grading_query"]
            assert J.build_descriptive_grading_query(t.qid, "RESP", t.answer) == up_q
        else:
            assert t.question == up_r[t.figure_id]["question"]
            resp = {str(t.figure_id): {"raw_question": t.raw_question, "response": "RESP"}}
            one = {str(t.figure_id): data_r[str(t.figure_id)]}
            up_q = RU.build_reasoning_grading_queries(one, resp)[str(t.figure_id)]["grading_query"]
            assert J.build_reasoning_grading_query(t.inst_category, t.raw_question, "RESP", t.answer) == up_q
