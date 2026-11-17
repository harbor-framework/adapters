"""Grader and naming tests. The judge is faked, so no API calls are made."""

import asyncio
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from gdp_pdf.adapter import GdpPdfAdapter, GdpPdfTask, _rubrics_from_row

GRADER_PATH = (
    Path(__file__).parents[1] / "src" / "gdp_pdf" / "task-template" / "tests" / "grader.py"
)
spec = importlib.util.spec_from_file_location("grader", GRADER_PATH)
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


class FakeClient:
    """Returns queued judge replies in order and records the prompts it saw."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, model, messages, response_format):
        self.prompts.append(messages[0]["content"])
        content = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def verdict(score):
    return json.dumps({"score": score, "rationale": "because"})


RUBRICS = [{"id": "r1", "criterion": "States A."}, {"id": "r2", "criterion": "States B."}]


def run_grade(replies, rubrics=RUBRICS):
    client = FakeClient(replies)
    result = asyncio.run(grader.grade(client, "judge", "the answer", rubrics))
    return result["grades"], client


def test_all_points_pass():
    grades, _ = run_grade([verdict("1"), verdict("1")])
    assert grader.summarize(grades) == {"reward": 1.0, "mean_criteria": 1.0}


def test_one_point_fails():
    grades, _ = run_grade([verdict("1"), verdict("0")])
    assert grader.summarize(grades) == {"reward": 0.0, "mean_criteria": 0.5}


def test_judge_sees_only_answer_and_criterion():
    _, client = run_grade([verdict("1")], rubrics=RUBRICS[:1])
    prompt = client.prompts[0]
    assert "response: the answer," in prompt
    assert "criteria: States A.," in prompt


def test_unparseable_output_is_retried():
    grades, client = run_grade(["not json", "```json\n" + verdict("1") + "\n```"], rubrics=RUBRICS[:1])
    assert grades[0]["result"] == "pass"
    assert len(client.prompts) == 2


def test_point_unscored_after_all_retries():
    replies = ["bad"] * (grader.MAX_RETRIES + 1)
    grades, client = run_grade(replies, rubrics=RUBRICS[:1])
    assert grades[0]["result"] == "unscored"
    assert len(client.prompts) == grader.MAX_RETRIES + 1
    assert grader.summarize(grades) is None


@pytest.mark.parametrize(
    "raw",
    ['{"score": true, "rationale": "x"}', '{"score": "1"}', '{"score": "high", "rationale": "x"}', "[1]"],
)
def test_strict_parse_rejects(raw):
    with pytest.raises(grader.ParseError):
        grader.parse_verdict(raw)


@pytest.mark.parametrize(
    ("score", "expected"),
    [("1", True), ("0", False), ("0.99995", True), ("0.99994", False), ("2", True)],
)
def test_pass_threshold(score, expected):
    assert grader.passes(Decimal(score)) is expected


def test_missing_answer_scores_zero_without_judge(tmp_path):
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps(RUBRICS))
    out = tmp_path / "out"
    import sys

    argv = sys.argv
    sys.argv = ["grader", "--answer", str(tmp_path / "none.md"), "--rubric", str(rubric), "--out-dir", str(out)]
    try:
        assert grader.main() == 0
    finally:
        sys.argv = argv
    assert json.loads((out / "reward.json").read_text()) == {"reward": 0.0, "mean_criteria": 0.0}


def test_rubric_columns_are_ordered_and_blank_ones_dropped():
    row = {
        "rubric - 10. criterion": "ten",
        "rubric - 2. criterion": "two",
        "rubric - 3. criterion": None,
        "rubric - 2. criterion_type": "ignored",
    }
    assert _rubrics_from_row(row) == [
        {"id": "r2", "criterion": "two"},
        {"id": "r10", "criterion": "ten"},
    ]


def test_names_are_stable_and_hide_upstream_ids():
    tasks = [
        GdpPdfTask("bbb", "HR", "p", "x.pdf", []),
        GdpPdfTask("aaa", "HR", "p", "y.pdf", []),
        GdpPdfTask("ccc", "STEM/Research", "p", "z.pdf", []),
    ]
    names = GdpPdfAdapter.harbor_names(tasks)
    assert names == {"aaa": "hr-01", "bbb": "hr-02", "ccc": "stem-research-01"}
    assert names == GdpPdfAdapter.harbor_names(list(reversed(tasks)))


# Tasks per domain upstream (100 in total; legal-03 is excluded from the dataset).
DOMAIN_SIZES = {
    "construction": 10, "engineering": 10, "finance-investing": 9, "healthcare": 11,
    "hr": 9, "insurance": 9, "legal": 7, "manufacturing-supply-chains": 10,
    "real-estate": 10, "stem-research": 15,
}

# The 30 tasks the parity experiments ran on.
PARITY_TASKS = {
    "construction-01", "construction-07", "construction-10",
    "engineering-05", "engineering-08", "engineering-09",
    "finance-investing-04", "finance-investing-05", "finance-investing-07",
    "healthcare-04", "healthcare-06", "healthcare-10",
    "hr-03", "hr-08", "hr-09",
    "insurance-02", "insurance-03", "insurance-05",
    "legal-02", "legal-04", "legal-06",
    "manufacturing-supply-chains-02", "manufacturing-supply-chains-05",
    "manufacturing-supply-chains-09",
    "real-estate-02", "real-estate-06", "real-estate-08",
    "stem-research-06", "stem-research-07", "stem-research-15",
}


def test_parity_split_is_the_subset_parity_ran_on():
    names = [f"{d}-{i:02d}" for d, n in DOMAIN_SIZES.items() for i in range(1, n + 1)]
    names.remove("legal-03")
    assert len(names) == 99
    assert GdpPdfAdapter.parity_names(names) == PARITY_TASKS
    assert GdpPdfAdapter.parity_names(list(reversed(names))) == PARITY_TASKS


def test_unknown_split_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        GdpPdfAdapter(tmp_path, split="lite")
