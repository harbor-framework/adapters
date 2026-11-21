import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from inspect_ai.model import ChatMessageAssistant, ChatCompletionChoice, ModelOutput, ModelUsage
from inspect_ai.tool import ToolCall, ToolFunction

from chess_puzzles.api_probe import probe, run_probe, submission_tool


@pytest.mark.parametrize('forced_works', [True, False])
async def test_probe_requests_and_failure_record(tmp_path, monkeypatch, forced_works):
    requests = []
    counts = []
    settings = json.loads(Path('parity_settings.json').read_text())
    settings['token_count_mode'] = 'provider'  # This fake tests the native-count path.
    class FakeModel:
        def __init__(self, **kwargs):
            assert kwargs['max_retries'] == 0
            assert kwargs['api_key'] == 'only-in-memory-fake-key'
            self.streaming = kwargs['streaming']
            self.api = self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def count_tokens(self, messages):
            counts.append(messages)
            return 30
        async def generate(self, messages, tools, choice, config):
            requests.append((self.streaming, choice, config.max_tokens))
            assert tools[0].name == 'submit_answer'
            calls = [ToolCall(id='probe', function='submit_answer', arguments={'answer': 'b1c3'})] if forced_works else None
            return ModelOutput(model='offline-test', choices=[ChatCompletionChoice(
                message=ChatMessageAssistant(content='', tool_calls=calls), stop_reason='stop'
            )], usage=ModelUsage(input_tokens=30, output_tokens=10, total_tokens=40))
    monkeypatch.setattr('chess_puzzles.api_probe.get_model', lambda *args, **kwargs: FakeModel(**kwargs))
    dest = tmp_path / 'probe'
    if forced_works:
        result = await probe(settings, 'only-in-memory-fake-key', dest)
        assert result['status'] == 'complete'
        assert requests == [(True, 'auto', 64), (False, ToolFunction('submit_answer'), 256),
                            (True, ToolFunction('submit_answer'), 256)]
    else:
        with pytest.raises(RuntimeError, match='Forced'):
            await probe(settings, 'only-in-memory-fake-key', dest)
        result = json.loads((dest / 'result.json').read_text())
        assert result['status'] == 'incomplete'
        assert result['failed_stage'] == 'forced_nonstreaming'
        assert len(requests) == 2
    assert len(counts) == 1
    assert result['counts_as_parity'] is False
    assert 'only-in-memory-fake-key' not in (dest / 'result.json').read_text()


def test_probe_plan_does_not_request_key_or_create_files(tmp_path):
    settings = json.loads(Path('parity_settings.json').read_text())
    def no_key():
        raise AssertionError('Dry run requested a key')
    run_probe(settings, tmp_path / 'probe', False, no_key)
    assert list(tmp_path.iterdir()) == []


def test_probe_keeps_upstream_tool_definition():
    tool = submission_tool(None)
    assert tool.description.endswith('The conversation will end immediately.')
    assert tool.parameters.required == ['answer']


@pytest.mark.parametrize('count_mode', ['provider', 'local'])
async def test_probe_real_provider_serializes_explicit_forced_requests(tmp_path, monkeypatch, count_mode):
    import socket
    from inspect_ai.model._providers.anthropic import AnthropicAPI
    requests = []
    def no_network(*args, **kwargs):
        raise AssertionError('Offline probe test attempted a network connection')
    monkeypatch.setattr(socket.socket, 'connect', no_network)
    async def count(self, messages, config=None):
        return 30
    async def capture(self, request, streaming, tools, config):
        requests.append((request, streaming))
        output = ModelOutput(model='claude-haiku-5-5', choices=[ChatCompletionChoice(
            message=ChatMessageAssistant(content='', tool_calls=[ToolCall(
                id='probe', function='submit_answer', arguments={'answer': 'b1c3'}
            )]), stop_reason='stop'
        )], usage=ModelUsage(input_tokens=30, output_tokens=10, total_tokens=40))
        return {'offline': True}, output
    monkeypatch.setattr(AnthropicAPI, 'count_tokens', count)
    monkeypatch.setattr(AnthropicAPI, '_perform_request_and_continuations', capture)
    settings = json.loads(Path('parity_settings.json').read_text())
    settings['base_url'] = 'http://127.0.0.1:1'
    settings['token_count_mode'] = count_mode
    result = await probe(settings, 'offline-provider-test-key', tmp_path / 'probe')
    assert result['status'] == 'complete'
    assert result['token_counting']['mode'] == count_mode
    assert ('provider count_tokens endpoint' in result['not_covered']) == (count_mode == 'local')
    assert [stream for _, stream in requests] == [True, False, True]
    assert [req['max_tokens'] for req, _ in requests] == [64, 256, 256]
    assert requests[0][0]['tool_choice'] == {'type': 'auto'}
    for req, _ in requests[1:]:
        assert req['tool_choice'] == {'type': 'tool', 'name': 'submit_answer'}
        assert 'thinking' not in req
