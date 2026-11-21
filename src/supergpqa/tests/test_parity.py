"""Parity transport evidence, ambiguity handling and paired reporting checks."""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from supergpqa import direct
from supergpqa.parity import freeze, summarize


def fake_response(content="Answer: B", **message_fields):
    return {
        "model": "gpt-6-luna-2026-09-22",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        "choices": [
            {"message": {"content": content, **message_fields}, "finish_reason": "stop"}
        ],
    }


def mock_api(monkeypatch, response):
    context = MagicMock()
    context.__enter__.return_value = context
    context.read.return_value = json.dumps(response).encode()
    opener = MagicMock()
    opener.open.return_value = context
    monkeypatch.setattr(direct, "build_opener", lambda *_: opener)
    monkeypatch.setenv("SUPERGPQA_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("SUPERGPQA_BASE_URL", "https://example.test/v1")
    return opener


def test_completed_resume_uses_saved_response_without_second_call(
    monkeypatch, tmp_path
):
    opener = mock_api(monkeypatch, fake_response("Answer: B\r\n"))
    assert direct.complete("question", tmp_path) == "Answer: B\r\n"
    assert direct.complete("question", tmp_path) == "Answer: B\r\n"
    assert opener.open.call_count == 1
    request = opener.open.call_args.args[0]
    body = json.loads(request.data)
    assert body["messages"] == [{"role": "user", "content": "question"}]
    assert "tools" not in body
    assert "test-only-not-a-real-key" not in "".join(
        p.read_text() for p in tmp_path.iterdir()
    )
    with pytest.raises(ValueError, match="different configuration"):
        direct.complete("different question", tmp_path)
    (tmp_path / "response.txt").write_text("tampered")
    with pytest.raises(ValueError, match="inconsistent"):
        direct.complete("question", tmp_path)


@pytest.mark.parametrize(
    "response", [fake_response(None), fake_response("", tool_calls=[{}]), {}]
)
def test_invalid_response_is_failure_and_never_silently_retried(
    monkeypatch, tmp_path, response
):
    opener = mock_api(monkeypatch, response)
    with pytest.raises(RuntimeError, match="API call failed"):
        direct.complete("question", tmp_path)
    assert json.loads((tmp_path / "call.json").read_text())["status"] == "failed"
    with pytest.raises(RuntimeError, match="previous call"):
        direct.complete("question", tmp_path)
    assert opener.open.call_count == 1


def test_empty_text_is_a_real_answer_not_transport_failure(monkeypatch, tmp_path):
    mock_api(monkeypatch, fake_response(""))
    assert direct.complete("question", tmp_path) == ""
    assert json.loads((tmp_path / "call.json").read_text())["status"] == "complete"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/v1",
        "https://u:p@example.test/v1",
        "https://example.test/v1?key=x",
        "",
    ],
)
def test_endpoint_rejects_credentials_and_non_https(url):
    with pytest.raises(ValueError):
        direct.endpoint_url(url)


def test_redirect_never_forwards_authorization():
    with pytest.raises(RuntimeError, match="redirect refused"):
        direct.NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://another.test"
        )


def test_summary_uses_between_run_sample_sem_and_observed_ranges(tmp_path):
    for side, scores in {
        "original": [0.4, 0.5, 0.6],
        "harbor": [0.6, 0.7, 0.8],
    }.items():
        for index, score in enumerate(scores, 1):
            direct.save_json(
                tmp_path / f"run-{index}" / side / "summary.json", {"accuracy": score}
            )
    report = summarize(tmp_path)
    assert report["ranges_overlap"]  # Boundary contact counts as overlap.
    assert report["original"]["sample_sem"] == pytest.approx(0.1 / (3**0.5))
    assert report["harbor"]["mean"] == pytest.approx(0.7)


def test_frozen_experiment_refuses_changed_settings(tmp_path):
    path = tmp_path / "runtime.json"
    freeze(path, {"concurrency": 4})
    freeze(path, {"concurrency": 4})
    with pytest.raises(ValueError, match="configuration changed"):
        freeze(path, {"concurrency": 6})


def test_wrapper_writes_verbatim_response_and_token_usage(monkeypatch, tmp_path):
    # Requires Harbor on the test runtime; the standalone adapter keeps it external.
    from harbor.models.agent.context import AgentContext

    from supergpqa.harbor_agent import SuperGPQADirectAgent

    mock_api(monkeypatch, fake_response("Answer: B\r\n"))
    saved = {}

    class Environment:
        async def upload_file(self, source_path, target_path):
            saved[target_path] = Path(source_path).read_bytes()

    agent = SuperGPQADirectAgent(
        logs_dir=tmp_path, model_name="gpt-6-luna", skip_model_parsing=True
    )
    context = AgentContext()
    asyncio.run(agent.run("question", Environment(), context))
    assert saved == {"/app/answer.txt": b"Answer: B\r\n"}
    assert context.n_input_tokens == 5
    assert context.n_output_tokens == 3


def test_provider_version_change_stops_experiment(monkeypatch, tmp_path):
    response = fake_response()
    response["model"] = "unexpected-new-model-version"
    mock_api(monkeypatch, response)
    with pytest.raises(RuntimeError, match="API call failed"):
        direct.complete("question", tmp_path)
    assert json.loads((tmp_path / "call.json").read_text())["status"] == "failed"
