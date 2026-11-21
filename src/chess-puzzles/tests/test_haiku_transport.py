"""Inspect's request serialization only: intercept before any network request."""
import pytest

from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model
from inspect_ai.tool import ToolFunction, ToolInfo


@pytest.mark.parametrize('choice', ['auto', ToolFunction('submit_answer')])
async def test_default_haiku_keeps_tool_choice_without_network(choice, monkeypatch):
    class Captured(BaseException):
        pass

    import socket
    def no_network(*args, **kwargs):
        raise AssertionError('Offline request test attempted a network connection')
    monkeypatch.setattr(socket.socket, 'connect', no_network)
    model = get_model('anthropic/claude-haiku-5-5', api_key='offline-placeholder',
                      base_url='http://127.0.0.1:1', memoize=False)
    captured = []
    async def capture(request, *args, **kwargs):
        captured.append(request)
        raise Captured()
    monkeypatch.setattr(model.api, '_perform_request_and_continuations', capture)
    with pytest.raises(Captured):
        await model.api.generate([ChatMessageUser(content='offline test')],
                                 [ToolInfo(name='submit_answer', description='Submit a move')],
                                 choice, GenerateConfig(max_tokens=16000))
    request = captured[0]
    assert request['model'] == 'claude-haiku-5-5'
    assert request['tool_choice'] == ({'type': 'auto'} if choice == 'auto' else
                                     {'type': 'tool', 'name': 'submit_answer'})
    assert 'thinking' not in request  # Native model default; not thinking-disabled.
    assert not {'temperature', 'top_p', 'top_k'} & request.keys()
