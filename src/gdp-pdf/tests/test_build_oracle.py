"""Oracle builder loop tests. Writer and judge are faked."""

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from gdp_pdf.adapter import GdpPdfAdapter, GdpPdfTask

SCRIPT = Path(__file__).parents[1] / "scripts" / "build_oracle.py"
spec = importlib.util.spec_from_file_location("build_oracle", SCRIPT)
build_oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_oracle)


class Fake:
    """Hands out queued replies and records the prompts it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, model, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        content = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def verdict(score, why="because"):
    return json.dumps({"score": score, "rationale": why})


TASK = GdpPdfTask("t1", "HR", "What is X?", "x.pdf", [{"id": "r1", "criterion": "Says X is 5."}])


def build(writer, judge, max_rounds=3, confirm=2):
    return asyncio.run(
        build_oracle.build_one(TASK, "doc text", writer, "w", judge, "j", max_rounds, confirm)
    )


def test_accepted_only_after_confirm_passes():
    writer = Fake(["X is 5."])
    judge = Fake([verdict("1")] * 3)
    answer, log = build(writer, judge)
    assert answer == "X is 5."
    assert len(log) == 1 and len(log[0]["gradings"]) == 3


def test_failed_point_is_sent_back_with_rationale():
    writer = Fake(["X is big.", "X is 5."])
    judge = Fake([verdict("0", "no number given"), verdict("1"), verdict("1"), verdict("1")])
    answer, log = build(writer, judge)
    assert answer == "X is 5."
    revise_prompt = writer.prompts[1]
    assert "Says X is 5." in revise_prompt and "no number given" in revise_prompt
    assert "X is big." in revise_prompt


def test_flaky_pass_is_not_accepted():
    # Passes once, then fails on the confirming grade: must be revised.
    writer = Fake(["X is 5ish.", "X is 5."])
    judge = Fake([verdict("1"), verdict("0", "hedged"), verdict("1"), verdict("1"), verdict("1")])
    answer, log = build(writer, judge)
    assert answer == "X is 5."
    assert len(log) == 2


def test_gives_up_after_max_rounds():
    writer = Fake(["a", "b", "c"])
    judge = Fake([verdict("0")] * 2)
    answer, log = build(writer, judge, max_rounds=2)
    assert answer is None
    assert len(log) == 2


def test_adapter_reads_oracle_dir(tmp_path):
    (tmp_path / "t1.md").write_text("X is 5.\n")
    adapter = GdpPdfAdapter(tmp_path / "out", oracle_dir=tmp_path)
    assert adapter._oracle_answer(TASK) == "X is 5.\n"
    assert GdpPdfAdapter(tmp_path / "out")._oracle_answer(TASK) is None
    other = GdpPdfTask("t2", "HR", "p", "y.pdf", [])
    assert adapter._oracle_answer(other) is None
