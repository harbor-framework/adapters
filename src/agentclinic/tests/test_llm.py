import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agentclinic import llm


class FakeOpenAI:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                status, content = outer.replies.pop(0)
                ok = {
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                    "choices": [{"message": {"content": content}}],
                }
                payload = json.dumps(ok if status == 200 else {"error": content})
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload.encode())

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def fake():
    servers = []

    def make(replies):
        server = FakeOpenAI(replies)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_chat_sends_upstream_request_shape(fake):
    server = fake([(200, "I have  double\n vision.")])
    client = llm.ChatClient(base_url=server.url, api_key="sk-test", retry_sleep=0)
    assert client("gpt-4o-mini", "SYS", "USER") == "I have double vision."
    request = server.requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert request["auth"] == "Bearer sk-test"
    assert request["body"] == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}],
        "temperature": 0.05,
        "max_tokens": 200,
    }


def test_chat_retries_then_succeeds(fake):
    server = fake([(503, "busy"), (429, "slow down"), (200, "Yes")])
    client = llm.ChatClient(base_url=server.url, api_key="k", tries=3, retry_sleep=0)
    assert client("m", "s", "u") == "Yes"
    assert len(server.requests) == 3


def test_chat_raises_after_tries(fake):
    server = fake([(500, "boom")] * 2)
    client = llm.ChatClient(base_url=server.url, api_key="k", tries=2, retry_sleep=0)
    with pytest.raises(llm.LLMError, match="2 attempts"):
        client("m", "s", "u")


def test_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("AGENTCLINIC_LLM_TRIES", "4")
    monkeypatch.setenv("AGENTCLINIC_LLM_RETRY_SLEEP", "0.5")
    client = llm.ChatClient.from_env()
    assert (client.base_url, client.api_key, client.tries, client.retry_sleep) == (
        "https://example.test/v1",
        "sk-env",
        4,
        0.5,
    )


def test_from_env_defaults(monkeypatch):
    for name in ("OPENAI_BASE_URL", "AGENTCLINIC_LLM_TRIES", "AGENTCLINIC_LLM_RETRY_SLEEP"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    client = llm.ChatClient.from_env()
    assert (client.base_url, client.tries, client.retry_sleep, client.deadline) == (
        "https://api.openai.com/v1",
        30,
        5.0,
        50.0,
    )


def test_from_env_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="OPENAI_API_KEY"):
        llm.ChatClient.from_env()


def test_chat_retries_after_dropped_connection(monkeypatch):
    import http.client
    import io

    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        if len(calls) == 2:
            raise ConnectionResetError(54, "Connection reset by peer")
        return Response(json.dumps({"choices": [{"message": {"content": "Yes"}}]}).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    client = llm.ChatClient(base_url="http://x/v1", api_key="k", tries=3, retry_sleep=0)
    assert client("m", "s", "u") == "Yes"
    assert len(calls) == 3


def test_chat_gives_up_at_deadline(fake):
    server = fake([(503, "busy")] * 50)
    client = llm.ChatClient(base_url=server.url, api_key="k", tries=50, retry_sleep=0.05, deadline=0.2)
    with pytest.raises(llm.LLMError, match="deadline"):
        client("m", "s", "u")
    assert len(server.requests) < 50


def test_chat_null_content_is_retried_then_fails(fake):
    server = fake([(200, None), (200, None)])
    client = llm.ChatClient(base_url=server.url, api_key="k", tries=2, retry_sleep=0)
    with pytest.raises(llm.LLMError, match="2 attempts"):
        client("m", "s", "u")


def test_default_deadline_fits_inside_tool_timeouts():
    assert llm.DEFAULT_DEADLINE <= 50


def test_chat_records_served_model(monkeypatch):
    import io

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    body = {"model": "gpt-4o-mini-2024-07-18", "choices": [{"message": {"content": "Yes"}}]}
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda request, timeout: Response(json.dumps(body).encode()))
    client = llm.ChatClient(base_url="http://x/v1", api_key="k", retry_sleep=0)
    assert client.last_model is None
    client("gpt-4o-mini", "s", "u")
    assert client.last_model == "gpt-4o-mini-2024-07-18"


def test_chat_accumulates_usage(fake):
    server = fake([(200, "a"), (200, "b")])
    client = llm.ChatClient(base_url=server.url, api_key="k", retry_sleep=0)
    client("m", "s", "u")
    client("m", "s", "u")
    assert client.usage == {"prompt_tokens": 20, "completion_tokens": 6}


def test_chat_records_finish_reason(monkeypatch):
    import io

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    body = {"choices": [{"message": {"content": "Yes"}, "finish_reason": "stop"}], "usage": "malformed"}
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda request, timeout: Response(json.dumps(body).encode()))
    client = llm.ChatClient(base_url="http://x/v1", api_key="k", tries=1, retry_sleep=0)
    assert client("m", "s", "u") == "Yes"
    assert client.last_finish_reason == "stop"
