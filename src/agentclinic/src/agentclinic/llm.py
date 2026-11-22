import http.client
import json
import os
import time
import urllib.error
import urllib.request

try:
    from . import prompts
except ImportError:
    import prompts

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TRIES = 30
DEFAULT_RETRY_SLEEP = 5.0
DEFAULT_DEADLINE = 50.0


class LLMError(RuntimeError):
    pass


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class ChatClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "",
        tries: int = DEFAULT_TRIES,
        retry_sleep: float = DEFAULT_RETRY_SLEEP,
        timeout: float = 120.0,
        deadline: float = DEFAULT_DEADLINE,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tries = tries
        self.retry_sleep = retry_sleep
        self.timeout = timeout
        self.deadline = deadline
        self.last_model: str | None = None
        self.last_finish_reason: str | None = None
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    @classmethod
    def from_env(cls) -> "ChatClient":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not set")
        return cls(
            base_url=os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL,
            api_key=api_key,
            tries=int(os.environ.get("AGENTCLINIC_LLM_TRIES") or DEFAULT_TRIES),
            retry_sleep=float(os.environ.get("AGENTCLINIC_LLM_RETRY_SLEEP") or DEFAULT_RETRY_SLEEP),
            deadline=float(os.environ.get("AGENTCLINIC_LLM_DEADLINE") or DEFAULT_DEADLINE),
        )

    def _record(self, payload: dict, choice: dict) -> None:
        self.last_model = payload.get("model")
        self.last_finish_reason = choice.get("finish_reason")
        usage = payload.get("usage")
        if isinstance(usage, dict):
            for key in self.usage:
                self.usage[key] += _as_int(usage.get(key))

    def __call__(self, model: str, system: str, user: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": prompts.TEMPERATURE,
                "max_tokens": prompts.MAX_TOKENS,
            }
        ).encode("utf-8")
        last_error = ""
        started = time.monotonic()
        for attempt in range(self.tries):
            remaining = self.deadline - (time.monotonic() - started)
            if remaining <= 0:
                raise LLMError(
                    f"chat completion hit the {self.deadline:.0f} s deadline after {attempt} attempts: {last_error}"
                )
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=min(self.timeout, remaining)) as response:
                    payload = json.loads(response.read())
                choice = payload["choices"][0]
                content = prompts.normalize_response(choice["message"]["content"])
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}: {exc.read()[:300]!r}"
            except (OSError, http.client.HTTPException, KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                self._record(payload, choice)
                return content
            if attempt + 1 < self.tries:
                if time.monotonic() - started + self.retry_sleep >= self.deadline:
                    raise LLMError(
                        f"chat completion hit the {self.deadline:.0f} s deadline after {attempt + 1} attempts: {last_error}"
                    )
                time.sleep(self.retry_sleep)
        raise LLMError(f"chat completion failed after {self.tries} attempts: {last_error}")
