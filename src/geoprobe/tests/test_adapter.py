import json
from importlib.resources import files
import shutil
import tomllib

import pytest

from geoprobe.adapter import GeoProbeAdapter, task_id
from geoprobe.grader import grade
from geoprobe.metric import aggregate
from geoprobe.public_runner import submission_from_report
from geoprobe.rewards import encode_metrics
from geoprobe.sources import safe_relative, sha256
from geoprobe.upstream.w1_scoring import parse_submission, score_case


def test_vendored_scorers_match_the_pinned_source_receipt():
    upstream = files("geoprobe") / "upstream"
    manifest = json.loads((upstream / "SOURCES.json").read_text())
    for source, expected in manifest["unmodified_files"].items():
        relative = source.removeprefix("src/embodied_harness/")
        assert sha256(upstream / relative) == expected


def test_sparse_error_aggregation_does_not_reward_missing_answers():
    case = {"benchmark": "vlm_motion_fixed"}
    rows = [encode_metrics(case, {"submission_valid": True, "absolute_error_cm": 4}),
            encode_metrics(case, {"submission_valid": True, "absolute_error_cm": 8}),
            encode_metrics(case, {"submission_valid": False}), None,
            encode_metrics({"benchmark": "vlm_focal"}, {"submission_valid": True, "focal_ape_pct": 20})]
    result = aggregate(rows)
    assert result["vlm_motion_fixed__absolute_error_cm"] == 6
    assert result["vlm_motion_fixed__absolute_error_cm__n"] == 2
    assert result["vlm_motion_fixed__valid_fraction"] == 2 / 3
    assert result["vlm_focal__focal_ape_pct"] == 20
    assert result["missing_trials"] == 1
    assert "mean" not in result


def test_native_agent_failure_is_not_an_infrastructure_retry():
    assert submission_from_report({"ok": True, "native_result": {"prediction": {"f": 10}}}) == {"f": 10}
    assert submission_from_report({"outcome": "budget_exhausted"}) is None
    for outcome in ["timeout", "agent_failure"]:
        assert submission_from_report({"outcome": outcome, "event_log_paths": {
            "episode_loop": {"turns": [{"stage": "execution", "execution_ok": False}]}}}) is None
    for report in [{"outcome": "runtime_failure"}, {"outcome": "agent_failure", "event_log_paths": {
            "episode_loop": {"turns": [{"stage": "model_completion", "error": "ModelRequestError"}]}}}]:
        with pytest.raises(RuntimeError, match="infrastructure"):
            submission_from_report(report)


@pytest.mark.parametrize("value", ["../outside", "/absolute", "images/../../outside", "images\\outside"])
def test_asset_paths_cannot_escape(value):
    with pytest.raises(ValueError):
        safe_relative(value)


def test_all_reference_answers_use_native_scorer(cases, tmp_path):
    rows = []
    for case in cases:
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(case["gt"]))
        metrics, reward = grade(case, answer)
        assert metrics == score_case(parse_submission(case["gt"]), case)
        assert metrics["submission_valid"], case["sample_id"]
        value = metrics[case["primary_metric"]]
        assert value is True if case["primary_metric"] == "exact_match" else abs(value) <= 2e-6
        rows.append(reward)
    result = aggregate(rows)
    assert result["recorded_cases"] == 168
    assert result["missing_trials"] == 0
    assert all(value == 1 for key, value in result.items() if key.endswith("__valid_fraction"))


def test_malformed_answers_are_invalid_not_zero_error(cases, tmp_path):
    answer = tmp_path / "answer.json"
    for payload in ["{", "null", "{}", '{"x": NaN}', '{"x": true}']:
        answer.write_text(payload)
        for case in cases:
            metrics, reward = grade(case, answer)
            assert metrics["submission_valid"] is False
            assert reward == {case["benchmark"] + "__cases": 1, case["benchmark"] + "__valid": 0}
    answer.unlink()
    assert grade(cases[0], answer)[0]["submission_valid"] is False


def test_incorrect_finite_answer_preserves_native_error(cases, tmp_path):
    case = next(c for c in cases if c["benchmark"] == "vlm_focal")
    answer = tmp_path / "answer.json"
    answer.write_text(json.dumps({"f": case["gt"]["f"] * 2}))
    native, reward = grade(case, answer)
    assert native["focal_ape_pct"] == 100
    assert aggregate([reward])["vlm_focal__focal_ape_pct"] == 100
    assert native["passed"] is False


def test_task_isolation_stability_and_overwrite(cases, data_root, tmp_path):
    case = next(c for c in cases if len(c["images"]) == 2)
    output = tmp_path / "tasks"
    paths = GeoProbeAdapter(output, data_root, task_ids=[case["sample_id"]]).run()
    task = paths[0]
    config = tomllib.loads((task / "task.toml").read_text())
    assert config["task"]["name"] == "embodied-agent-arena/geoprobe-" + task_id(case["sample_id"])
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["artifacts"] == ["/workspace/answer.json"]
    assert len(config["task"]["authors"]) == 10
    public = json.loads((task / "environment/public-task.json").read_text())
    assert "gt" not in public and "provenance" not in public
    assert public["question"] == case["question"]
    assert [image["role"] for image in public["images"]] == [image["role"] for image in case["images"]]
    assert not list((task / "environment").rglob("case.json"))
    assert not list((task / "environment").rglob("answer.json"))
    assert not list((task / "environment").rglob("grader.py"))
    assert json.loads((task / "solution/answer.json").read_text()) == case["gt"]
    before = {str(path.relative_to(task)): sha256(path) for path in task.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="already exists"):
        GeoProbeAdapter(output, data_root, task_ids=[case["sample_id"]]).run()
    GeoProbeAdapter(output, data_root, overwrite=True, task_ids=[task.name]).run()
    after = {str(path.relative_to(task)): sha256(path) for path in task.rglob("*") if path.is_file()}
    assert before == after


def test_unknown_task_ids_fail_before_output(cases, data_root, tmp_path):
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="Unknown task"):
        GeoProbeAdapter(output, data_root, task_ids=["typo"]).run()
    assert not output.exists()


def test_corrupt_image_is_rejected_before_output(cases, data_root, tmp_path):
    local = tmp_path / "data"
    local.mkdir()
    for name in ["catalog.jsonl", "download_receipt.json"]:
        shutil.copyfile(data_root / name, local / name)
    selected = cases[0]
    for item in selected["images"]:
        image = local / item["path"]
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"corrupted image")
    output = tmp_path / "tasks"
    with pytest.raises(ValueError, match="checksum"):
        GeoProbeAdapter(output, local, task_ids=[selected["sample_id"]]).run()
    assert not output.exists()
