"""Tests for the file-commit-chain scenarios (interactive rebase, iterative committing).

The first part covers what the adapter derives from the commits of a chain:
the two patch files, the hunk listing and the commits quoted in the
instruction. The second part runs the verifier
(``task-template-file-commit-chain/tests/evaluate_history.py``) on the ``.git``
directory an agent could leave behind, with the LLM judge replaced by a
function that answers in a fixed way.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ADAPTER_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ADAPTER_SRC))

from gitgoodbench.adapter import (  # noqa: E402
    CHAIN_TEMPLATE_DIR,
    EXCLUDED_SAMPLES,
    TEMPLATE_DIR,
    GitGoodBenchAdapter,
    GitGoodBenchTask,
    read_as_text,
    remaining_hunks,
    without_sections_of,
)

BRANCH = "current-scenario-branch"
FILE = "src/app.py"
OTHER_FILE = "docs/notes.txt"
SEQUENCE_EDITOR = '#!/bin/bash\necho -e "break\\n$(cat "$1")" > "$1"\n'

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        sys.platform == "win32" or shutil.which("git") is None,
        reason="the scenarios are built with Git",
    ),
]


def git_env() -> dict[str, str]:
    return {
        **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "vcs-agent",
        "GIT_AUTHOR_EMAIL": "vcs@agent.takeover",
        "GIT_COMMITTER_NAME": "vcs-agent",
        "GIT_COMMITTER_EMAIL": "vcs@agent.takeover",
        "GIT_EDITOR": "true",
    }


def run_git(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**git_env(), **(env or {})},
        text=True,
        capture_output=True,
    )


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = run_git(*args, cwd=cwd, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class Upstream:
    """The project a sample was mined from: a commit and a chain of three
    commits that all change the same file."""

    def __init__(
        self, root: Path, attributes: str | None = None, mailmap: str | None = None
    ):
        self.path = root / "upstream"
        (self.path / "src").mkdir(parents=True)
        (self.path / "docs").mkdir()
        git("init", "-q", "-b", "main", cwd=self.path)
        lines = [f"line {i}" for i in range(1, 41)]
        self.write(FILE, lines)
        (self.path / OTHER_FILE).write_text("notes\n")
        if attributes is not None:
            (self.path / ".gitattributes").write_text(attributes)
        if mailmap is not None:
            (self.path / ".mailmap").write_text(mailmap)
        self.base = self.commit("root")

        lines[2] = "line 3 changed"
        self.write(FILE, lines)
        first = self.commit("change line 3")
        lines[30] = "line 31 changed"
        self.write(FILE, lines)
        (self.path / OTHER_FILE).write_text("notes\nmore notes\n")
        (self.path / "docs" / "new.txt").write_text("a new file\n")
        second = self.commit("change line 31 and the notes")
        lines[2] = "line 3 changed again"
        self.write(FILE, lines)
        third = self.commit("change line 3 again")
        self.commits = [first, second, third]
        self.newest = third
        self.url = self.path.as_uri()

    def write(self, name: str, lines: list[str]) -> None:
        (self.path / name).write_text("\n".join(lines) + "\n")

    def commit(self, message: str) -> str:
        git("add", "-A", cwd=self.path)
        git("commit", "-q", "-m", message, cwd=self.path)
        return git("rev-parse", "HEAD", cwd=self.path)

    def task(self, scenario_type: str) -> GitGoodBenchTask:
        return GitGoodBenchTask(
            task_id=f"scratch-file-commit-chain-0000-{scenario_type}",
            source_id="scratch_file_commit_chain_0000",
            repository="scratch/scratch",
            programming_language="python",
            difficulty="easy",
            scenario={
                "file": FILE,
                "times_seen_consecutively": 3,
                "purity": 0.8,
                "newest_commit": self.newest,
                "oldest_commit": self.commits[0],
            },
            source_dataset="test",
            scenario_type=scenario_type,
        )


@pytest.fixture
def upstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Upstream:
    project = Upstream(tmp_path)
    monkeypatch.setattr(
        GitGoodBenchTask, "repo_url", property(lambda self: project.url)
    )
    return project


# ------------------------------------------------------------------ adapter


def test_remaining_hunks_lists_hunks_without_headers():
    patch = (
        "diff --git a/f b/f\nindex 1..2 100644\n--- a/f\n+++ b/f\n"
        "@@ -1,2 +1,2 @@ def f():\n-a\n+b\n c\n@@ -9 +9 @@\n-x\n+y\n"
    )

    count, hunks = remaining_hunks(patch)

    assert count == 2
    assert hunks == "\nHUNK-1:\n-a\n+b\n c\n\nHUNK-2:\n-x\n+y"
    assert remaining_hunks("") == (0, "")


def test_without_sections_of_drops_the_file_of_the_scenario():
    patch = (
        "diff --git a/docs/notes.txt b/docs/notes.txt\n--- a\n+++ b\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/src/app.py b/src/app.py\n--- a\n+++ b\n@@ -1 +1 @@\n-c\n+d\n"
        "diff --git a/setup.py b/setup.py\n--- a\n+++ b\n@@ -1 +1 @@\n-e\n+f\n"
    )

    kept = without_sections_of("src/app.py", patch)

    assert "docs/notes.txt" in kept and "setup.py" in kept
    assert "src/app.py" not in kept
    # The original reads the patch in text mode before it filters it.
    assert read_as_text(b"a\r\nb\rc\n") == "a\nb\nc\n"


def test_file_commit_chain_sample_gives_two_tasks(tmp_path: Path):
    rows = [
        {
            "id": "scratch_file_commit_chain_0000",
            "name": "scratch/scratch",
            "programming_language": "python",
            "difficulty": "easy",
            "sample_type": "file_commit_chain",
            # The dataset stores the scenario as the text of a Python dict.
            "scenario": "{'file': 'a.py', 'times_seen_consecutively': 3, "
            f"'purity': 1.0, 'newest_commit': '{'f' * 40}'}}",
        },
        {
            "id": "scratch_merge_0000",
            "name": "scratch/scratch",
            "programming_language": "python",
            "sample_type": "merge",
            "scenario": {"merge_commit_hash": "0" * 40, "parents": ["1", "2"]},
        },
        {
            "id": next(k for k in EXCLUDED_SAMPLES if "file-commit-chain" in k),
            "name": "scratch/excluded",
            "programming_language": "kotlin",
            "sample_type": "file_commit_chain",
            "scenario": {},
        },
    ]

    tasks = GitGoodBenchAdapter(tmp_path).build_tasks(rows)
    assert [(t.task_id, t.scenario_type) for t in tasks] == [
        ("scratch-file-commit-chain-0000-chunk", "chunk"),
        ("scratch-file-commit-chain-0000-rebase", "rebase"),
        ("scratch-merge-0000", "merge"),
    ]

    only_rebase = GitGoodBenchAdapter(tmp_path, scenario_types=["rebase"])
    assert [t.task_id for t in only_rebase.build_tasks(rows)] == [
        "scratch-file-commit-chain-0000-rebase"
    ]
    # A sample id selects both of its tasks.
    by_sample = GitGoodBenchAdapter(
        tmp_path, task_ids=["scratch_file_commit_chain_0000"]
    )
    assert len(by_sample.select_tasks(tasks)) == 2
    with pytest.raises(ValueError):
        GitGoodBenchAdapter(tmp_path, scenario_types=["cherry-pick"])


def test_prepare_chain_derives_patches_and_history(upstream: Upstream, tmp_path: Path):
    adapter = GitGoodBenchAdapter(tmp_path / "out")
    bundle = tmp_path / "ground_truth.bundle"

    facts = adapter.prepare_chain(upstream.task("chunk"), bundle)

    assert facts.base_commit == upstream.base
    assert list(facts.commits) == upstream.commits
    assert list(facts.ground_truth_commits) == upstream.commits[::-1]
    assert facts.exit_commit == upstream.base
    # file_changes.patch holds the file of the scenario, all_changes.patch the
    # other files that existed before the chain. New files are in neither, as
    # in the original.
    file_changes = facts.file_changes.decode()
    assert file_changes.startswith(f"diff --git a/{FILE} b/{FILE}\n")
    assert "+line 3 changed again" in file_changes
    all_changes = facts.all_changes.decode()
    assert f"a/{OTHER_FILE}" in all_changes and FILE not in all_changes
    assert "new.txt" not in all_changes
    assert facts.hunk_count == 2
    assert facts.hunks.startswith("\nHUNK-1:\n")
    assert "\nHUNK-2:\n" in facts.hunks and "@@" not in facts.hunks
    # The commits of the rebase todo list, oldest first.
    for index, commit in enumerate(upstream.commits):
        assert f"<COMMIT-{index}>\ncommit {commit}\n" in facts.participating_commits
    assert bundle.stat().st_size > 0


def test_prepare_chain_reads_attributes_of_the_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The original diffs in a checkout, where .gitattributes applies."""
    project = Upstream(tmp_path, attributes="*.py -diff\n")
    monkeypatch.setattr(
        GitGoodBenchTask, "repo_url", property(lambda self: project.url)
    )

    facts = GitGoodBenchAdapter(tmp_path / "out").prepare_chain(project.task("chunk"))

    assert b"Binary files" in facts.file_changes
    assert facts.hunk_count == 0


def test_prepare_chain_reads_the_mailmap_of_the_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The original shows the commits in a checkout, where .mailmap applies."""
    project = Upstream(
        tmp_path, mailmap="Jane Doe <jane@example.org> <vcs@agent.takeover>\n"
    )
    monkeypatch.setattr(
        GitGoodBenchTask, "repo_url", property(lambda self: project.url)
    )

    facts = GitGoodBenchAdapter(tmp_path / "out").prepare_chain(project.task("rebase"))

    assert facts.participating_commits.count("Author: Jane Doe <jane@example.org>") == 3
    assert "vcs-agent" not in facts.participating_commits


def test_prepare_chain_refuses_what_the_original_cannot_set_up(
    upstream: Upstream, tmp_path: Path
):
    task = upstream.task("chunk")
    task.scenario["file"] = "docs/new.txt"  # does not exist before the chain
    with pytest.raises(RuntimeError, match="does not exist before the chain"):
        GitGoodBenchAdapter(tmp_path / "out").prepare_chain(task)


@pytest.mark.parametrize("scenario_type", ["chunk", "rebase"])
def test_generated_task(upstream: Upstream, tmp_path: Path, scenario_type: str):
    adapter = GitGoodBenchAdapter(tmp_path / "out")

    task_dir = adapter.generate_task(upstream.task(scenario_type))

    toml = tomllib.loads((task_dir / "task.toml").read_text())
    assert toml["task"]["name"].endswith(f"-{scenario_type}")
    assert toml["metadata"]["scenario_type"] == (
        "iterative_committing" if scenario_type == "chunk" else "interactive_rebase"
    )
    assert toml["metadata"]["file"] == FILE and toml["metadata"]["commits"] == 3
    assert toml["verifier"]["environment_mode"] == "separate"
    assert toml["verifier"]["env"] == {
        "OPENAI_API_KEY": "${OPENAI_API_KEY:-}",
        "OPENAI_BASE_URL": "${OPENAI_BASE_URL:-}",
        "JUDGE_MODEL": "${JUDGE_MODEL:-gpt-4o}",
        "ORACLE_MODE": "${ORACLE_MODE:-}",
    }
    assert toml["artifacts"] == [
        {"source": "/workspace/repo/.git", "destination": "repo.git"}
    ]

    instruction = (task_dir / "instruction.md").read_text()
    scenario = json.loads((task_dir / "environment" / "scenario.json").read_text())
    config = json.loads((task_dir / "tests" / "config.json").read_text())
    assert config["ground_truth_commits"] == upstream.commits[::-1]
    assert config["exit_commit"] == upstream.base
    assert config["newest_commit"] == upstream.newest
    environment = {p.name for p in (task_dir / "environment").iterdir()}
    solution = {p.name for p in (task_dir / "solution").iterdir()}
    if scenario_type == "chunk":
        assert "Process all of the following 2 hunks:" in instruction
        assert f"the changes to `{FILE}`" in instruction
        assert scenario["start_commit"] == upstream.base
        # The commits of the chain are not named anywhere in the image.
        assert not any(commit in json.dumps(scenario) for commit in upstream.commits)
        assert {"all_changes.patch", "file_changes.patch"} <= environment
        assert solution == {"solve.sh", "ground_truth.bundle"}
    else:
        assert "covers the last 3 commits" in instruction
        assert "length k<3" in instruction
        assert all(f"commit {commit}" in instruction for commit in upstream.commits)
        assert scenario["start_commit"] == upstream.newest
        assert scenario["commits"] == upstream.commits
        assert "all_changes.patch" not in environment
        assert solution == {"solve.sh"}
    assert not re.search(
        r"\{(programming_language|times_seen_consecutively|participating_commits"
        r"|file|number_of_remaining_hunks|remaining_hunks)\}",
        instruction,
    )
    assert {"Dockerfile", "setup_chain.py", "setup_scenario.py"} <= environment
    assert {p.name for p in (task_dir / "tests").iterdir()} == {
        "Dockerfile",
        "test.sh",
        "evaluate.py",
        "evaluate_history.py",
        "judge.py",
        "fetch_ground_truth.py",
        "config.json",
    }
    assert os.access(task_dir / "solution" / "solve.sh", os.X_OK)


def test_judge_prompts_are_the_original_ones():
    judge = load_module("judge", CHAIN_TEMPLATE_DIR / "tests" / "judge.py")

    assert judge.SYSTEM_PROMPT.startswith(
        "Please act as an impartial judge and evaluate the quality of the two\n"
    )
    # Sent as written in the original, doubled braces included.
    assert judge.SYSTEM_PROMPT.count("{{") == 3
    assert judge.user_prompt(["a", "b"], ["c"]) == (
        "\n        <HISTORY-1>\na\nb\n    </HISTORY-1>\n\n"
        "    <HISTORY-2>\nc\n    </HISTORY-2>"
    )
    assert judge.parse_verdict("{'evaluation_result': 'TIE', 'evaluation_reason': ''}")
    assert judge.parse_verdict('{"evaluation_result": "HISTORY-1"}')
    assert judge.parse_verdict("{{\n'evaluation_result': 'HISTORY-2'\n}}")
    assert judge.parse_verdict("no verdict") is None


# ----------------------------------------------------------------- verifier


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HandedOver:
    """A scenario in the state the task image leaves it in, and what the
    verifier container holds for it."""

    def __init__(self, root: Path, upstream: Upstream, scenario_type: str):
        self.root = root
        self.upstream = upstream
        self.scenario_type = scenario_type
        self.repo = root / "workspace" / "repo"
        self.repo.mkdir(parents=True)
        start = upstream.base if scenario_type == "chunk" else upstream.newest

        # environment/setup_chain.py: the history in an object store of its
        # own, the repository borrowing it.
        history = root / "history.git"
        history.mkdir()
        git("init", "-q", "--bare", cwd=history)
        git("fetch", "--no-tags", "--quiet", upstream.url, start, cwd=history)
        git("update-ref", "refs/scenario/start", start, cwd=history)
        git("init", "-q", cwd=self.repo)
        alternates = self.repo / ".git" / "objects" / "info" / "alternates"
        alternates.write_text(f"{history / 'objects'}\n")
        git("checkout", "-q", "-b", BRANCH, start, cwd=self.repo)
        if scenario_type == "rebase":
            editor = root / "sequence_editor.sh"
            editor.write_text(SEQUENCE_EDITOR)
            editor.chmod(0o755)
            git(
                "rebase",
                "-i",
                "HEAD~3",
                cwd=self.repo,
                env={"GIT_SEQUENCE_EDITOR": str(editor)},
            )

        # tests/fetch_ground_truth.py: the original commits, shallow.
        self.ground_truth = root / "ground-truth.git"
        self.ground_truth.mkdir()
        git("init", "-q", "--bare", cwd=self.ground_truth)
        git(
            "fetch",
            "--no-tags",
            "--quiet",
            "--depth=4",
            upstream.url,
            upstream.newest,
            cwd=self.ground_truth,
        )
        self.config = {
            "task_id": f"controls-file-commit-chain-0000-{scenario_type}",
            "scenario_type": scenario_type,
            "file": FILE,
            "times_seen_consecutively": 3,
            "newest_commit": upstream.newest,
            "exit_commit": upstream.base,
            "ground_truth_commits": upstream.commits[::-1],
        }

    def git(self, *args: str) -> str:
        return git(*args, cwd=self.repo)

    def commit_file(self, content: str, message: str) -> None:
        (self.repo / FILE).write_text(content)
        self.git("add", FILE)
        self.git("commit", "-q", "-m", message)

    def original_history(self) -> None:
        """What the oracle leaves behind."""
        if self.scenario_type == "rebase":
            self.git("rebase", "--continue")
        else:
            self.git("fetch", "--quiet", self.upstream.url, self.upstream.newest)
            self.git("merge", "--quiet", "--ff-only", "FETCH_HEAD")

    def verifier_input(self) -> Path:
        """The copy of ``.git`` the verifier container receives."""
        target = self.root / "verifier" / "repo"
        target.mkdir(parents=True)
        shutil.copytree(self.repo / ".git", target / ".git")
        return target


class Verifier:
    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch):
        self.evaluate = load_module("evaluate", TEMPLATE_DIR / "tests" / "evaluate.py")
        self.judge = load_module("judge", CHAIN_TEMPLATE_DIR / "tests" / "judge.py")
        self.module = load_module(
            "evaluate_history", CHAIN_TEMPLATE_DIR / "tests" / "evaluate_history.py"
        )
        self.logs = root / "logs"
        self.config_path = root / "config.json"
        self.monkeypatch = monkeypatch
        self.prompts: list[str] = []
        for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "JUDGE_MODEL", "ORACLE_MODE"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(self.evaluate, "LOG_DIR", self.logs)
        monkeypatch.setattr(self.module, "LOG_DIR", self.logs)
        monkeypatch.setattr(self.module, "CONFIG_PATH", self.config_path)

    def judge_prefers(self, preference: str, newest: str) -> None:
        """Replace the judge: "agent", "original" or "tie"."""

        def chat(system: str, user: str, timeout: float = 600.0) -> str:
            self.prompts.append(user)
            first = user.split("<HISTORY-1>\n", 1)[1]
            original_first = first.startswith(f"commit {newest}\n")
            if preference == "tie":
                verdict = "TIE"
            elif (preference == "original") == original_first:
                verdict = "HISTORY-1"
            else:
                verdict = "HISTORY-2"
            return json.dumps({"evaluation_result": verdict, "evaluation_reason": ""})

        self.monkeypatch.setattr(self.judge, "chat", chat)

    def run(self, scenario: HandedOver) -> tuple[int, str | None, dict]:
        self.config_path.write_text(json.dumps(scenario.config))
        self.monkeypatch.setattr(self.module, "REPO_DIR", scenario.verifier_input())
        self.monkeypatch.setattr(self.module, "GROUND_TRUTH_DIR", scenario.ground_truth)
        code = self.module.main()
        reward_file = self.logs / "reward.txt"
        reward = reward_file.read_text().strip() if reward_file.exists() else None
        details = json.loads((self.logs / "details.json").read_text())
        return code, reward, details


@pytest.fixture
def verifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Verifier:
    return Verifier(tmp_path, monkeypatch)


@pytest.fixture
def project(tmp_path: Path) -> Upstream:
    return Upstream(tmp_path)


@pytest.mark.parametrize("scenario_type", ["chunk", "rebase"])
def test_oracle_mode_accepts_the_original_history(
    tmp_path: Path, project: Upstream, verifier: Verifier, scenario_type: str
):
    scenario = HandedOver(tmp_path, project, scenario_type)
    scenario.original_history()
    verifier.monkeypatch.setenv("ORACLE_MODE", "true")

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "1")
    assert details["agent_commits"] == project.commits[::-1]
    assert "llm_responses" not in details


@pytest.mark.parametrize("scenario_type", ["chunk", "rebase"])
def test_the_original_history_is_a_tie_for_the_judge(
    tmp_path: Path, project: Upstream, verifier: Verifier, scenario_type: str
):
    """Without ORACLE_MODE the paper's rule applies to every history."""
    scenario = HandedOver(tmp_path, project, scenario_type)
    scenario.original_history()
    verifier.judge_prefers("tie", project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "0")
    assert len(verifier.prompts) == 2
    # Both histories are the same text, in both positions.
    first, second = verifier.prompts[0].split("</HISTORY-1>")
    assert first.split("<HISTORY-1>\n")[1].strip() in second
    assert [r.get("history_1") for r in details["llm_responses"]] == [
        "AGENT",
        "GROUND_TRUTH",
    ]


def test_rebase_that_is_not_concluded_is_not_solved(
    tmp_path: Path, project: Upstream, verifier: Verifier
):
    scenario = HandedOver(tmp_path, project, "rebase")
    verifier.monkeypatch.setenv("ORACLE_MODE", "true")
    verifier.judge_prefers("agent", project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "0")
    assert details["rebase_in_progress"] is True
    assert verifier.prompts == []


@pytest.mark.parametrize(
    "preference, expected", [("agent", "1"), ("original", "0"), ("tie", "0")]
)
def test_judge_decides_a_cleaned_up_history(
    tmp_path: Path,
    project: Upstream,
    verifier: Verifier,
    preference: str,
    expected: str,
):
    scenario = HandedOver(tmp_path, project, "rebase")
    # Meld the three commits into one with a new message.
    scenario.git("rebase", "--abort")
    scenario.git("reset", "-q", "--soft", project.base)
    scenario.git("commit", "-q", "-m", "REFACTOR: Rework lines 3 and 31")
    verifier.judge_prefers(preference, project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, expected)
    assert len(details["agent_commits"]) == 1
    assert len(verifier.prompts) == 2
    # Asked twice with the positions swapped.
    assert (
        "REFACTOR: Rework lines 3 and 31"
        in verifier.prompts[0].split("</HISTORY-1>")[0]
    )
    assert (
        "REFACTOR: Rework lines 3 and 31"
        in verifier.prompts[1].split("</HISTORY-1>")[1]
    )
    # The whole commits are shown, other files included.
    assert OTHER_FILE in verifier.prompts[0]
    assert (verifier.logs / "agent_history.txt").read_text().startswith("commit ")


def test_iterative_committing_shows_only_the_file_of_the_scenario(
    tmp_path: Path, project: Upstream, verifier: Verifier
):
    scenario = HandedOver(tmp_path, project, "chunk")
    final = git("show", f"{project.newest}:{FILE}", cwd=project.path) + "\n"
    scenario.commit_file(final, "UPDATE: Change lines 3 and 31")
    (scenario.repo / OTHER_FILE).write_text("notes\nmore notes\n")
    scenario.git("add", OTHER_FILE)
    scenario.git("commit", "-q", "-m", "UPDATE: Extend the notes")
    verifier.judge_prefers("agent", project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "1")
    assert len(details["agent_commits"]) == 2
    prompt = verifier.prompts[0]
    # Commit messages of every commit, diffs of the file of the scenario only.
    assert "UPDATE: Extend the notes" in prompt
    assert "change line 31 and the notes" in prompt
    assert f"diff --git a/{FILE} b/{FILE}" in prompt
    assert OTHER_FILE not in prompt and "new.txt" not in prompt


def test_histories_are_shown_with_the_mailmap_of_their_newest_commit(
    tmp_path: Path, verifier: Verifier
):
    project = Upstream(
        tmp_path, mailmap="Jane Doe <jane@example.org> <vcs@agent.takeover>\n"
    )
    scenario = HandedOver(tmp_path, project, "chunk")
    scenario.commit_file("rewritten\n", "UPDATE: Rewrite the file")
    verifier.judge_prefers("agent", project.newest)

    verifier.run(scenario)

    original = (verifier.logs / "ground_truth_history.txt").read_text()
    assert original.count("Author: Jane Doe <jane@example.org>") == 3
    assert "Author: Jane Doe" in (verifier.logs / "agent_history.txt").read_text()


def test_branch_that_left_the_scenario_is_not_solved(
    tmp_path: Path, project: Upstream, verifier: Verifier
):
    scenario = HandedOver(tmp_path, project, "chunk")
    scenario.git("checkout", "-q", "--orphan", "elsewhere")
    scenario.git("commit", "-q", "--allow-empty", "-m", "unrelated")
    scenario.git("branch", "-f", BRANCH, "elsewhere")
    verifier.judge_prefers("agent", project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "0")
    assert details["agent_commits"] is None
    assert verifier.prompts == []


def test_history_without_commits_is_left_to_the_judge(
    tmp_path: Path, project: Upstream, verifier: Verifier
):
    """As in the original, which builds an empty history and asks the judge."""
    scenario = HandedOver(tmp_path, project, "chunk")
    verifier.judge_prefers("original", project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "0")
    assert details["agent_commits"] == []
    assert len(verifier.prompts) == 2


def test_judge_that_cannot_be_asked_leaves_no_reward(
    tmp_path: Path, project: Upstream, verifier: Verifier
):
    scenario = HandedOver(tmp_path, project, "chunk")
    scenario.commit_file("rewritten\n", "UPDATE: Rewrite the file")
    verifier.logs.mkdir()
    (verifier.logs / "reward.txt").write_text("1\n")

    code, reward, details = verifier.run(scenario)

    assert code == 1 and reward is None
    assert "OPENAI_API_KEY is not set" in details["error"]


def test_original_history_is_read_without_the_agents_objects(
    tmp_path: Path, project: Upstream, verifier: Verifier
):
    """An object the agent stores under the id of an original commit must not
    change what the judge is shown as the original history."""
    scenario = HandedOver(tmp_path, project, "chunk")
    scenario.commit_file("rewritten\n", "UPDATE: Rewrite the file")
    forged = scenario.git("rev-parse", "HEAD")
    source = scenario.repo / ".git" / "objects" / forged[:2] / forged[2:]
    target = scenario.repo / ".git" / "objects" / project.newest[:2]
    target.mkdir(exist_ok=True)
    shutil.copyfile(source, target / project.newest[2:])
    verifier.judge_prefers("original", project.newest)

    code, reward, details = verifier.run(scenario)

    assert (code, reward) == (0, "0")
    original = (verifier.logs / "ground_truth_history.txt").read_text()
    assert "change line 3 again" in original and "Rewrite the file" not in original


# -------------------------------------------------------------- image build


def build_image(
    root: Path, upstream: Upstream, scenario: dict, patches: dict[str, bytes]
) -> tuple[subprocess.CompletedProcess, Path, Path]:
    """Run environment/setup_chain.py as the image build does, with the two
    directories of the image placed under ``root``."""
    repo = root / "workspace" / "repo"
    history = root / "opt" / "history.git"
    build = root / "build"
    build.mkdir()
    for path in (
        TEMPLATE_DIR / "environment" / "setup_scenario.py",
        CHAIN_TEMPLATE_DIR / "environment" / "setup_chain.py",
    ):
        text = path.read_text()
        text = text.replace('"/workspace/repo"', repr(str(repo)))
        text = text.replace('"/opt/scenario/history.git"', repr(str(history)))
        text = text.replace('"/tmp/sequence_editor.sh"', repr(str(root / "editor.sh")))
        (build / path.name).write_text(text)
    for name, content in patches.items():
        (build / name).write_bytes(content)
    (build / "scenario.json").write_text(
        json.dumps({"repo_url": upstream.url, **scenario})
    )
    result = subprocess.run(
        [sys.executable, "setup_chain.py", "scenario.json"],
        cwd=build,
        env=git_env(),
        text=True,
        capture_output=True,
    )
    return result, repo, history


def test_image_build_pauses_the_rebase_on_the_quoted_commits(
    tmp_path: Path, project: Upstream
):
    scenario = {
        "scenario_type": "rebase",
        "start_commit": project.newest,
        "times_seen_consecutively": 3,
        "commits": project.commits,
    }

    result, repo, _ = build_image(tmp_path, project, scenario, {})

    assert result.returncode == 0, result.stderr
    assert (repo / ".git" / "rebase-merge" / "interactive").exists()
    assert git("rev-parse", "HEAD", cwd=repo) == project.base
    assert git("rev-parse", BRANCH, cwd=repo) == project.newest
    todo = (repo / ".git" / "rebase-merge" / "git-rebase-todo").read_text()
    assert [line.split()[1] for line in todo.splitlines()] == project.commits
    # The repository borrows the history and holds no commit of its own.
    assert (repo / ".git" / "objects" / "info" / "alternates").exists()


def test_image_build_fails_when_the_rebase_differs_from_the_instruction(
    tmp_path: Path, project: Upstream
):
    scenario = {
        "scenario_type": "rebase",
        "start_commit": project.newest,
        "times_seen_consecutively": 3,
        "commits": project.commits[::-1],
    }

    result, _, _ = build_image(tmp_path, project, scenario, {})

    assert result.returncode != 0
    assert "differs from the commits quoted in the instruction" in result.stderr


def test_image_build_of_iterative_committing_has_no_original_commits(
    tmp_path: Path, project: Upstream, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        GitGoodBenchTask, "repo_url", property(lambda self: project.url)
    )
    facts = GitGoodBenchAdapter(tmp_path / "out").prepare_chain(project.task("chunk"))
    scenario = {"scenario_type": "chunk", "start_commit": facts.base_commit}
    patches = {
        "file_changes.patch": facts.file_changes,
        "all_changes.patch": facts.all_changes,
    }

    result, repo, history = build_image(tmp_path, project, scenario, patches)

    assert result.returncode == 0, result.stderr
    assert git("rev-parse", BRANCH, cwd=repo) == project.base
    assert git("status", "--porcelain", cwd=repo).splitlines() == [
        "?? all_changes.patch",
        "?? file_changes.patch",
    ]
    for commit in project.commits:
        for store in (repo, history):
            assert run_git("cat-file", "-e", commit, cwd=store).returncode != 0
    # The patches give the files of the newest commit, as the instruction says.
    git("apply", "--whitespace=fix", "file_changes.patch", cwd=repo)
    git("apply", "--allow-empty", "--whitespace=fix", "all_changes.patch", cwd=repo)
    for name in (FILE, OTHER_FILE):
        assert (repo / name).read_text() == git(
            "show", f"{project.newest}:{name}", cwd=project.path
        ) + "\n"
