"""Verifier controls for the asta-bench adapter.

These tests execute the *generated* ``tests/test.sh`` + scorer of real task
directories outside Docker (absolute container paths are rewritten into a
temporary sandbox) and check the verifier contract documented in
``asta_bench/benchmarks/base.py``:

* the oracle scores 1.0 through the generated verifier;
* a reward planted before verification is never trusted;
* a missing / unreadable / garbage answer is a scored 0, never a pass;
* a verifier failure (broken config, judge outage) records *no* reward and
  exits non-zero instead of fabricating a 0;
* DS-1000 snippets cannot pass by exiting the process early.

No network and no API key are needed: the oracle paths never call a judge,
and the judge-outage control injects a stub ``litellm`` that always raises.

Point ``ASTA_BENCH_TASKS_DIR`` at a directory of generated tasks, e.g.::

    uv run asta-bench --output-dir /tmp/asta-tasks --limit 2
    ASTA_BENCH_TASKS_DIR=/tmp/asta-tasks uv run --with pytest pytest tests -q

The task-directory tests are skipped when the variable is unset; the DS-1000
tests are self-contained and always run.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from asta_bench.benchmarks import ds1000 as ds1000_builder

_CONTAINER_ROOTS = ("logs", "tests", "app", "solution")
_PATH_RE = re.compile(
    r"(?<![\w./-])/(" + "|".join(_CONTAINER_ROOTS) + r")(?=[/\"'\s)]|$)"
)

_TASKS_DIR = os.environ.get("ASTA_BENCH_TASKS_DIR")

# Families whose non-oracle scoring calls an LLM judge through litellm.
_JUDGE_FAMILIES = ("sqa", "arxivdigestables-clean", "discoverybench", "e2e-bench")

# A well-formed, non-oracle answer per judge family: it must get past answer
# parsing so that the scorer reaches the (stubbed, failing) judge call.
_WELL_FORMED_ANSWERS = {
    "sqa": json.dumps(
        {
            "sections": [
                {
                    "title": "Background",
                    "text": "Transformers use attention [1].",
                    "citations": [
                        {
                            "id": "[1]",
                            "snippets": ["Attention is all you need."],
                            "title": "Attention Is All You Need",
                        }
                    ],
                }
            ]
        }
    ),
    "arxivdigestables-clean": json.dumps(
        {"cell_values": [{"paper_id": "1", "column_name": "Method", "cell_value": "x"}]}
    ),
    "discoverybench": json.dumps(
        {"hypothesis": "A is associated with B.", "workflow": "Fit a regression."}
    ),
    "e2e-bench": json.dumps(
        {"results": {"report": "We ran it.", "code": [], "artifacts": []}}
    ),
    # Semantic paper-finder queries LLM-judge every submitted paper.
    "paper-finder": json.dumps(
        {
            "output": {
                "results": [
                    {"paper_id": "999999999", "markdown_evidence": "A relevant paper."}
                ]
            }
        }
    ),
}


def _rewrite(text: str, root: Path) -> str:
    return _PATH_RE.sub(lambda m: f"{root}/{m.group(1)}", text)


class Sandbox:
    """A task's tests/ + solution/ copied into a fake container root."""

    def __init__(self, task_dir: Path, root: Path) -> None:
        self.root = root
        for name in _CONTAINER_ROOTS:
            (root / name).mkdir(parents=True, exist_ok=True)
        (root / "logs" / "verifier").mkdir(exist_ok=True)
        (root / "logs" / "agent").mkdir(exist_ok=True)
        for sub in ("tests", "solution"):
            src = task_dir / sub
            if not src.is_dir():
                continue
            for f in src.iterdir():
                if not f.is_file():
                    continue
                dst = root / sub / f.name
                if f.suffix in (".sh", ".py"):
                    dst.write_text(_rewrite(f.read_text(encoding="utf-8"), root))
                    dst.chmod(0o755)
                else:
                    shutil.copy2(f, dst)
        # The ds1000 template ships a placeholder solution file that only
        # exists in the container for oracle runs; start without it.
        placeholder = root / "solution" / "solution.py"
        if placeholder.exists():
            placeholder.unlink()

    @property
    def answer(self) -> Path:
        return self.root / "app" / "answer.txt"

    @property
    def reward_file(self) -> Path:
        return self.root / "logs" / "verifier" / "reward.txt"

    def plant_reward(self, value: str = "1") -> None:
        self.reward_file.write_text(value + "\n")

    def _run(self, script: Path, extra_pythonpath: Path | None = None):
        env = dict(os.environ)
        # `python3` inside test.sh must be the interpreter running pytest.
        env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            env.pop(key, None)
        if extra_pythonpath is not None:
            env["PYTHONPATH"] = str(extra_pythonpath)
        return subprocess.run(
            ["bash", str(script)],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def solve(self):
        return self._run(self.root / "solution" / "solve.sh")

    def verify(self, extra_pythonpath: Path | None = None):
        return self._run(self.root / "tests" / "test.sh", extra_pythonpath)

    def reward(self) -> float | None:
        if not self.reward_file.exists():
            return None
        return float(self.reward_file.read_text().strip())


def _task_dirs() -> list[Path]:
    if not _TASKS_DIR:
        return []
    root = Path(_TASKS_DIR)
    return sorted(
        p for p in root.rglob("task.toml") if (p.parent / "tests" / "test.sh").exists()
    )


def _family(task_dir: Path) -> str:
    cfg = task_dir / "tests" / "config.json"
    if cfg.exists():
        family = json.loads(cfg.read_text()).get("family")
        if family:
            return family
    return "ds1000" if task_dir.name.startswith("ds1000-") else "unknown"


_TASKS = [p.parent for p in _task_dirs()]
_needs_tasks = pytest.mark.skipif(
    not _TASKS, reason="set ASTA_BENCH_TASKS_DIR to a directory of generated tasks"
)


def _ids(tasks: list[Path]) -> list[str]:
    return [t.name for t in tasks]


def _non_ds1000(tasks: list[Path]) -> list[Path]:
    # Generated DS-1000 tasks need the per-problem scientific stack to run
    # their code_context; they are covered by the self-contained tests below.
    return [t for t in tasks if _family(t) != "ds1000"]


def _is_super_auto(task_dir: Path) -> bool:
    cfg = task_dir / "tests" / "config.json"
    return cfg.exists() and json.loads(cfg.read_text()).get("super_split") == "Auto"


def _offline_oracle(tasks: list[Path]) -> list[Path]:
    # A SUPER-Auto oracle is a real environment setup (clone, install, download)
    # followed by the verifier running the entrypoint; it needs the task
    # container and the network.  See test_super_auto_oracle_answer_is_runnable.
    return [t for t in _non_ds1000(tasks) if not _is_super_auto(t)]


_AUTO_TASKS = [t for t in _TASKS if _is_super_auto(t)]


@_needs_tasks
@pytest.mark.parametrize("task_dir", _AUTO_TASKS, ids=_ids(_AUTO_TASKS))
def test_super_auto_oracle_answer_is_runnable(task_dir: Path) -> None:
    """Static half of the Auto oracle: solve.sh submits a command the verifier
    would accept for execution (the execution itself needs the container)."""
    solve = (task_dir / "solution" / "solve.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in solve
    body = solve.split("<<'SUPER_AUTO_ANSWER_EOF'\n", 1)[1]
    answer = json.loads(body.split("\nSUPER_AUTO_ANSWER_EOF", 1)[0])
    assert set(answer) == {"command", "cwd"}
    assert answer["cwd"].startswith("/")
    entrypoint = json.loads((task_dir / "tests" / "config.json").read_text())["entrypoint"]
    name = os.path.basename(entrypoint)
    command = answer["command"]
    assert name in command or (
        name.replace(".py", "").replace("/", ".") in command and "python -m" in command
    )
    # No nonce and no gold in the verifier config: nothing to short-circuit on.
    cfg = json.loads((task_dir / "tests" / "config.json").read_text())
    assert not any("nonce" in k or "gold" in k for k in cfg)


@_needs_tasks
@pytest.mark.parametrize(
    "task_dir", _offline_oracle(_TASKS), ids=_ids(_offline_oracle(_TASKS))
)
def test_oracle_scores_one(task_dir: Path, tmp_path: Path) -> None:
    sb = Sandbox(task_dir, tmp_path)
    solved = sb.solve()
    assert solved.returncode == 0, solved.stderr
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 1.0, result.stderr


@_needs_tasks
@pytest.mark.parametrize("task_dir", _non_ds1000(_TASKS), ids=_ids(_non_ds1000(_TASKS)))
def test_planted_reward_is_not_trusted_when_answer_missing(
    task_dir: Path, tmp_path: Path
) -> None:
    sb = Sandbox(task_dir, tmp_path)
    sb.plant_reward("1")
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 0.0


@_needs_tasks
@pytest.mark.parametrize("task_dir", _non_ds1000(_TASKS), ids=_ids(_non_ds1000(_TASKS)))
@pytest.mark.parametrize(
    "payload",
    [b"", b"\xff\xfe\x00garbage\x80", b"not json at all", b"{" * 5000, b"[1, 2, 3]"],
    ids=["empty", "non-utf8", "prose", "deep-braces", "json-array"],
)
def test_garbage_answer_never_passes(
    task_dir: Path, tmp_path: Path, payload: bytes
) -> None:
    sb = Sandbox(task_dir, tmp_path)
    sb.plant_reward("1")
    sb.answer.write_bytes(payload)
    result = sb.verify()
    # Either a scored 0, or a verifier error with no reward -- never a pass,
    # and never the planted value.
    reward = sb.reward()
    if result.returncode == 0:
        assert reward == 0.0, result.stderr
    else:
        assert reward is None, result.stderr


@_needs_tasks
@pytest.mark.parametrize("task_dir", _non_ds1000(_TASKS), ids=_ids(_non_ds1000(_TASKS)))
def test_answer_path_is_directory(task_dir: Path, tmp_path: Path) -> None:
    sb = Sandbox(task_dir, tmp_path)
    sb.plant_reward("1")
    sb.answer.mkdir()
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 0.0


@_needs_tasks
@pytest.mark.parametrize("task_dir", _non_ds1000(_TASKS), ids=_ids(_non_ds1000(_TASKS)))
def test_verifier_failure_records_no_reward(task_dir: Path, tmp_path: Path) -> None:
    sb = Sandbox(task_dir, tmp_path)
    sb.plant_reward("1")
    sb.answer.write_text("{}")
    (sb.root / "tests" / "config.json").write_text("{ this is not json")
    result = sb.verify()
    assert result.returncode != 0
    assert sb.reward() is None


def _judge_tasks() -> list[Path]:
    out = []
    for t in _TASKS:
        fam = _family(t)
        if fam in _JUDGE_FAMILIES or fam == "e2e-bench-hard":
            out.append(t)
        elif fam == "paper-finder":
            cfg = json.loads((t / "tests" / "config.json").read_text())
            if cfg.get("query_type") == "semantic":
                out.append(t)
    return out


@_needs_tasks
@pytest.mark.parametrize("task_dir", _judge_tasks(), ids=_ids(_judge_tasks()))
def test_judge_outage_records_no_reward(task_dir: Path, tmp_path: Path) -> None:
    family = _family(task_dir)
    answer = _WELL_FORMED_ANSWERS["e2e-bench" if family.startswith("e2e") else family]
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "litellm.py").write_text(
        "drop_params = True\n"
        "class APIConnectionError(Exception):\n    pass\n"
        "def completion(*a, **k):\n    raise APIConnectionError('judge outage')\n"
        "async def acompletion(*a, **k):\n    raise APIConnectionError('judge outage')\n"
    )
    sb = Sandbox(task_dir, tmp_path / "root")
    sb.plant_reward("1")
    sb.answer.write_text(answer)
    result = sb.verify(extra_pythonpath=stub)
    assert result.returncode != 0, result.stderr
    assert sb.reward() is None, result.stderr


# --- DS-1000: self-contained controls ---------------------------------------

_DS1000_CODE_CONTEXT = '''
exec_context = r"""
a = 1
b = 2
[insert]
"""

def test_execution(solution: str):
    code = exec_context.replace("[insert]", solution)
    env = {}
    exec(code, env)
    assert env["result"] == 3
'''


def _ds1000_task(tmp_path: Path) -> Path:
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "solution").mkdir()
    (task / "tests" / "config.json").write_text(
        json.dumps({"code_context": _DS1000_CODE_CONTEXT, "prompt": "add a and b"})
    )
    (task / "tests" / "test.sh").write_text(ds1000_builder._TEST_SH_TEMPLATE)
    shutil.copy2(ds1000_builder._DS1000_RUN_TEST_SRC, task / "tests" / "run_test.py")
    (task / "task.toml").write_text("")
    return task


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("<code>result = a + b</code>", 1.0),
        ("Here you go:\n<code>\nresult = a + b\n</code>\nDone.", 1.0),
        ("```python\nresult = a + b\n```", 1.0),
        ("<code>result = a - b</code>", 0.0),
        ("<code>result = (</code>", 0.0),
        ("<code>import os\nos._exit(0)</code>", 0.0),
        ("<code>import sys\nsys.exit(0)</code>", 0.0),
        ("<code>raise SystemExit(0)</code>", 0.0),
        ("<code>import time\nresult = 3\nprint('x' * 10)</code>", 1.0),
    ],
    ids=[
        "correct",
        "correct-with-prose",
        "correct-fenced",
        "wrong",
        "syntax-error",
        "os-exit-0",
        "sys-exit-0",
        "systemexit-0",
        "correct-with-stdout",
    ],
)
def test_ds1000_bridge_answer_is_graded(
    tmp_path: Path, answer: str, expected: float
) -> None:
    sb = Sandbox(_ds1000_task(tmp_path), tmp_path / "root")
    sb.plant_reward("1")
    sb.answer.write_text(answer)
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == expected, result.stderr


def test_ds1000_oracle_solution_file_is_graded(tmp_path: Path) -> None:
    sb = Sandbox(_ds1000_task(tmp_path), tmp_path / "root")
    (sb.root / "solution" / "solution.py").write_text("result = a + b\n")
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 1.0


def test_ds1000_missing_answer_scores_zero(tmp_path: Path) -> None:
    sb = Sandbox(_ds1000_task(tmp_path), tmp_path / "root")
    sb.plant_reward("1")
    result = sb.verify()
    assert result.returncode == 0, result.stderr
    assert sb.reward() == 0.0


def test_ds1000_broken_config_records_no_reward(tmp_path: Path) -> None:
    sb = Sandbox(_ds1000_task(tmp_path), tmp_path / "root")
    sb.plant_reward("1")
    sb.answer.write_text("<code>result = a + b</code>")
    (sb.root / "tests" / "config.json").write_text("{ not json")
    result = sb.verify()
    assert result.returncode != 0
    assert sb.reward() is None
