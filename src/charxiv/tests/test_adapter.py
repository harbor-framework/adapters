"""Unit tests for the CharXiv adapter.

Tests that compare against the upstream CharXiv code need a local checkout of
princeton-nlp/CharXiv@7ebe88f; point CHARXIV_UPSTREAM_DIR at it (they are
skipped otherwise).
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
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


_JUDGE_DIR: Path | None = None


def judge_dir() -> Path:
    """A tests/ directory laid out as in a generated task (judge + constants)."""
    global _JUDGE_DIR
    if _JUDGE_DIR is not None:
        return _JUDGE_DIR
    import tempfile

    d = _JUDGE_DIR = Path(tempfile.mkdtemp(prefix="charxiv-judge-"))
    shutil.copy2(TEMPLATE_TESTS / "judge.py", d / "judge.py")
    shutil.copy2(A.UPSTREAM_CONSTANTS_FILE, d / "charxiv_constants.py")
    return d


def load_judge():
    # judge.py loads charxiv_constants.py by explicit path from its own directory
    spec = importlib.util.spec_from_file_location("charxiv_judge", judge_dir() / "judge.py")
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
    paths = A.CharxivAdapter(output_dir=out, source_dir=source_dir).run()
    assert len(paths) == 10
    t = out / "charxiv-reasoning-5"
    cfg = tomllib.loads((t / "task.toml").read_text())
    assert cfg["version"] == "1.0"
    assert cfg["task"]["name"] == "princeton-nlp/charxiv-reasoning-5"
    assert cfg["task"]["authors"][0]["name"] == "Zirui Wang"
    assert "OPENAI_API_KEY" in cfg["verifier"]["env"]
    instr = (t / "instruction.md").read_text()
    assert "/app/images/chart.jpg" in instr and "/app/answer.txt" in instr
    assert "0.25" not in instr.replace("2 decimal", "")  # no answer leak
    assert [p.name for p in (t / "environment" / "images").iterdir()] == ["chart.jpg"]
    assert "COPY images/chart.jpg /app/images/chart.jpg" in (t / "environment" / "Dockerfile").read_text()
    # separate verifier: answer collected as an artifact, judge image built from tests/
    assert cfg["verifier"]["environment_mode"] == "separate"
    assert cfg["artifacts"] == [{"source": "/app/answer.txt"}]
    assert "COPY . /tests/" in (t / "tests" / "Dockerfile").read_text()
    assert "openai" not in (t / "environment" / "Dockerfile").read_text()
    assert "0.25" in (t / "solution" / "solve.sh").read_text()
    assert json.loads((t / "tests" / "config.json").read_text())["ground_truth"] == "0.25"
    assert (t / "tests" / "charxiv_constants.py").exists()
    for p in out.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".toml", ".sh"} or p.name == "Dockerfile":
            assert "{{" not in p.read_text(), p
    # no answers anywhere in the agent-visible environment
    env_text = (t / "environment" / "Dockerfile").read_text()
    assert "0.25" not in env_text


def test_no_upstream_id_in_agent_visible_files(source_dir, tmp_path):
    """Instruction and environment must not reveal the figure id or the source."""
    out = tmp_path / "out"
    A.CharxivAdapter(output_dir=out, source_dir=source_dir).run()
    for task_dir in out.iterdir():
        cfg = json.loads((task_dir / "tests" / "config.json").read_text())
        fid = str(cfg["figure_id"])
        visible = [task_dir / "instruction.md"] + sorted((task_dir / "environment").rglob("*"))
        for p in visible:
            if not p.is_file():
                continue
            assert fid not in p.name, p
            if p.suffix != ".jpg":
                text = p.read_text().lower()
                for word in ("charxiv", "princeton", "arxiv", "huggingface", "github"):
                    assert word not in text, (p, word)
        instr = (task_dir / "instruction.md").read_text()
        assert f"{fid}.jpg" not in instr


def test_limit_overwrite_taskids(source_dir, tmp_path):
    out = tmp_path / "out"
    assert len(A.CharxivAdapter(output_dir=out, source_dir=source_dir, limit=3).run()) == 3
    with pytest.raises(FileExistsError):
        A.CharxivAdapter(output_dir=out, source_dir=source_dir, limit=1).run()
    A.CharxivAdapter(output_dir=out, source_dir=source_dir, limit=1, overwrite=True).run()
    p = A.CharxivAdapter(output_dir=tmp_path / "o2", source_dir=source_dir,
                         task_ids=["charxiv-reasoning-0"]).run()
    assert [x.name for x in p] == ["charxiv-reasoning-0"]
    p = A.CharxivAdapter(output_dir=tmp_path / "o3", source_dir=source_dir,
                         modes=("reasoning",)).run()
    assert len(p) == 2


def test_unmatched_task_ids_exit_nonzero(source_dir, tmp_path):
    r = subprocess.run(
        [sys.executable, "-m", "charxiv.main", "--output-dir", str(tmp_path / "o"),
         "--source-dir", str(source_dir), "--task-ids", "charxiv-reasoning-424242"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "charxiv-reasoning-424242" in r.stderr
    assert not (tmp_path / "o").exists() or not any((tmp_path / "o").iterdir())


def test_missing_source_data_has_context(tmp_path):
    with pytest.raises(FileNotFoundError, match="must contain data"):
        A.load_tasks(A.CharXivSource(source_dir=tmp_path))


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


def test_parity_split(source_dir, tmp_path):
    assert A.parity_figure_ids(list(range(1000))) == A.parity_figure_ids(list(range(1000)))
    assert len(A.parity_figure_ids(list(range(1000)))) == 100
    p = A.CharxivAdapter(output_dir=tmp_path / "par", source_dir=source_dir, split="parity").run()
    assert len(p) == 10  # fixture has only 2 charts -> all kept


# ---------------------------------------------------------------- verifier integrity (B1-B3)

CFG_R = {"mode": "reasoning", "inst_category": 1, "raw_question": "q", "ground_truth": "Joint-CNN"}


def _run_main(J, tmp_path, answer_setup, chat_fn=None, cfg=CFG_R):
    tmp_path.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    answer = tmp_path / "app" / "answer.txt"
    answer.parent.mkdir(exist_ok=True)
    answer_setup(answer, cfg_path)
    rc = J.main(config_path=cfg_path, answer_path=answer, log_dir=log_dir, chat_fn=chat_fn)
    reward = log_dir / "reward.txt"
    return rc, (reward.read_text().strip() if reward.exists() else None), log_dir


def _never(*a):
    raise AssertionError("judge must not be called")


def test_main_exact_and_missing(tmp_path):
    J = load_judge()
    assert _run_main(J, tmp_path, lambda a, c: a.write_text("Joint-CNN\n"), _never)[:2] == (0, "1")
    assert _run_main(J, tmp_path / "m", lambda a, c: None, _never)[:2] == (0, "0")


def test_symlinked_answer_scores_zero(tmp_path):
    """B2: answer.txt -> config.json must not leak the ground truth to the judge."""
    J = load_judge()
    rc, reward, log_dir = _run_main(J, tmp_path, lambda a, c: a.symlink_to(c), _never)
    assert (rc, reward) == (0, "0")
    assert json.loads((log_dir / "judgment.json").read_text())["method"] == "agent_fault"
    # also a symlink to a file holding the exact ground truth
    def link_to_gt(a, c):
        (a.parent / "gt").write_text("Joint-CNN")
        a.symlink_to(a.parent / "gt")
    assert _run_main(J, tmp_path / "b", link_to_gt, _never)[:2] == (0, "0")


def test_non_regular_or_oversized_answer_scores_zero(tmp_path):
    J = load_judge()
    assert _run_main(J, tmp_path / "d", lambda a, c: a.mkdir(), _never)[:2] == (0, "0")
    assert _run_main(J, tmp_path / "f", lambda a, c: os.mkfifo(a), _never)[:2] == (0, "0")
    big = lambda a, c: a.write_text("Joint-CNN" + " " * (J.MAX_ANSWER_BYTES + 1))
    assert _run_main(J, tmp_path / "g", big, _never)[:2] == (0, "0")
    if os.geteuid() != 0:
        def unreadable(a, c):
            a.write_text("Joint-CNN")
            a.chmod(0)
        assert _run_main(J, tmp_path / "u", unreadable, _never)[:2] == (0, "0")


def test_judge_infrastructure_failure_writes_no_reward(tmp_path, monkeypatch):
    """B1: no judge reply -> exit 2 and no reward file (Harbor verifier error)."""
    J = load_judge()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rc, reward, log_dir = _run_main(J, tmp_path, lambda a, c: a.write_text("wrong"))
    assert (rc, reward) == (2, None)
    assert "OPENAI_API_KEY" in json.loads((log_dir / "judgment.json").read_text())["error"]

    def down(p, m):
        raise ConnectionError("unreachable")
    assert _run_main(J, tmp_path / "n", lambda a, c: a.write_text("wrong"), down)[:2] == (2, None)
    # a broken config is a verifier error too, never a score
    assert _run_main(J, tmp_path / "c", lambda a, c: a.write_text("x"), _never,
                     cfg={"mode": "nope", "ground_truth": "y"})[:2] == (2, None)


def test_judge_has_no_agent_controllable_paths():
    """B3: no sys.path edits, no env-var overrides of input/output paths."""
    src = (TEMPLATE_TESTS / "judge.py").read_text()
    assert "sys.path" not in src
    assert "CHARXIV_ANSWER_PATH" not in src and "CHARXIV_LOG_DIR" not in src
    assert "spec_from_file_location" in src


def _fake_tests_tree(tmp_path):
    """Run test.sh against a scratch root by rewriting its absolute paths."""
    root = tmp_path / "root"
    tests = root / "tests"
    tests.mkdir(parents=True)
    d = judge_dir()
    for name in ("judge.py", "charxiv_constants.py"):
        shutil.copy2(d / name, tests / name)
    (tests / "config.json").write_text(json.dumps(CFG_R))
    (root / "logs" / "verifier").mkdir(parents=True)
    (root / "app").mkdir()
    script = (TEMPLATE_TESTS / "test.sh").read_text()
    script = script.replace("/logs/verifier", str(root / "logs" / "verifier"))
    script = script.replace("/tests", str(tests))
    script = script.replace("/usr/local/bin/python3", sys.executable)
    (tests / "test.sh").write_text(script)
    # judge.py's fixed /app and /logs paths are redirected for this test only
    jp = tests / "judge.py"
    jp.write_text(jp.read_text()
                  .replace('Path("/app/answer.txt")', f'Path("{root}/app/answer.txt")')
                  .replace('Path("/logs/verifier")', f'Path("{root}/logs/verifier")'))
    return root, tests


def test_test_sh_removes_prewritten_reward_and_planted_files(tmp_path):
    """B1 + B3 at the shell level: stale rewards removed, unshipped files deleted."""
    root, tests = _fake_tests_tree(tmp_path)
    vdir = root / "logs" / "verifier"
    (vdir / "reward.json").write_text('{"reward": 1}')
    (vdir / "reward.txt").write_text("1")
    (tests / "json.py").write_text("raise SystemExit('planted module imported')")
    (tests / "openai").mkdir()
    (tests / "openai" / "__init__.py").write_text("raise SystemExit('planted')")
    (root / "app" / "answer.txt").write_text("definitely wrong")
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    r = subprocess.run(["bash", str(tests / "test.sh")], capture_output=True, text=True, env=env)
    assert not (vdir / "reward.json").exists()
    assert not (tests / "json.py").exists() and not (tests / "openai").exists()
    # wrong answer + no judge key -> verifier error, and the stale reward is gone
    assert r.returncode == 2, r.stderr
    assert not (vdir / "reward.txt").exists()

    (vdir / "reward.json").write_text('{"reward": 1}')
    (root / "app" / "answer.txt").write_text("Joint-CNN")
    r = subprocess.run(["bash", str(tests / "test.sh")], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert not (vdir / "reward.json").exists()
    assert (vdir / "reward.txt").read_text().strip() == "1"


def test_test_sh_hardening_lines():
    sh = (TEMPLATE_TESTS / "test.sh").read_text()
    assert sh.startswith("#!/bin/bash\n")
    assert "rm -f /logs/verifier/reward.txt /logs/verifier/reward.json" in sh
    assert "/usr/local/bin/python3 -I -B /tests/judge.py" in sh
