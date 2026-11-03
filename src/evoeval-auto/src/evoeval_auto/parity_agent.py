"""EvoEval code-generation agent (parity agent).

The original EvoEval benchmark has no agent: it sends one chat-completion request per
problem and evaluates the sanitized reply. This Harbor agent reproduces that harness for
API chat models so the Harbor tasks can be compared with the original pipeline:

* prompt and request: ``codegen/model.py::OpenAIChatDecoder`` and
  ``evoeval/util/api_request.py::create_chatgpt_config`` (system message
  "You are a helpful assistant.", user message
  "Please complete the following code snippet.\\n```\\n{prompt}\\n```",
  ``max_tokens = num_tokens(message) + max_new_tokens``, greedy ``temperature=0``, ``n=1``)
* post-processing: ``tool/sanitize.py`` (no ``--eof``), which keeps the target function
  and prepends the prompt's preamble (imports and helpers)

Upstream commit: evo-eval/evoeval@d5ca3104ec30b99f1076f51d4476eb4c3f29effa.

The only setting that differs from upstream is ``max_new_tokens`` (upstream: 512). The
parity model is a reasoning model whose reasoning tokens count against ``max_tokens``,
so 512 new tokens produce empty answers. The same value is used on the original side
(see the original-side fork).

Usage (from the repository root)::

    PYTHONPATH=src/evoeval-auto/src harbor run -p datasets/evoeval-auto \
        --agent evoeval_auto.parity_agent:EvoEvalCodegenAgent \
        -m openai/deepseek-v4.1-flash -e daytona --env-file oracle.env

The agent takes the upstream prompt verbatim from the first ```python block of the task
instruction (the adapter writes it there unchanged), calls the model from the Harbor
host, and writes the sanitized code to ``/workspace/solution.py``.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

SOLUTION_PATH = "/workspace/solution.py"
GENERATION_TEMPLATE = "Please complete the following code snippet.\n```\n{prompt}\n```"
SYSTEM_MESSAGE = "You are a helpful assistant."
ENTRY_POINT_RE = re.compile(r"Complete the Python function `([A-Za-z_][A-Za-z0-9_]*)`")
PROMPT_RE = re.compile(r"```python\n(.*?)\n```\n", re.DOTALL)


# --------------------------------------------------------------------------------------
# Upstream helpers (copied from evoeval/util/api_request.py and tool/sanitize.py)
# --------------------------------------------------------------------------------------
def num_tokens_from_messages(message, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    import tiktoken

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if isinstance(message, list):
        # use last message.
        num_tokens = len(encoding.encode(message[0]["content"]))
    else:
        num_tokens = len(encoding.encode(message))
    return num_tokens


def create_chatgpt_config(
    message,
    max_tokens: int,
    temperature: float = 1,
    batch_size: int = 1,
    system_message: str = SYSTEM_MESSAGE,
    model: str = "gpt-3.5-turbo",
) -> dict:
    return {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "n": batch_size,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": message},
        ],
    }


def _extract_function(code, target_func):
    def remove_last_line_until_parse(code):
        try:
            tree = ast.parse(code)
        except Exception:  # upstream uses a bare except; ast.parse raises Exception subclasses
            if "\n" in code:
                code = code.rsplit("\n", 1)[0]
                return remove_last_line_until_parse(code)
            else:
                return None
        return tree

    tree = remove_last_line_until_parse(code)
    if tree is None:  # fail to parse
        return ""

    # return the target function only
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name == target_func:
                return ast.unparse(node)
    return ""


def _to_four_space_indents(old_code):
    new_code = ""
    for line in old_code.splitlines():
        lspace = len(line) - len(line.lstrip())
        if lspace == 3:
            new_code += " "
        new_code += line + "\n"
    return new_code


def sanitize(old_code: str, prompt: str, entry_point: str) -> str:
    """Single-file version of ``tool/sanitize.py::sanitize_folder`` (no --eof, the
    folder name does not contain "chatgpt")."""
    def_left = "def " + entry_point + "("

    imports = prompt.split(def_left)[0]

    new_code = imports + def_left + old_code.split(def_left)[-1]
    chunks = new_code.split(def_left)  # imports + def_left + {def_right + impl}

    if len(chunks) == 2:
        new_code = def_left + chunks[-1]  # fn + impl

    new_code = _to_four_space_indents(new_code)

    # extract the target function and remove lines that are not indented
    new_code = _extract_function(new_code, entry_point)

    if len(chunks) == 2:
        new_code = chunks[0] + new_code
    return new_code


# --------------------------------------------------------------------------------------
# Harbor agent
# --------------------------------------------------------------------------------------
class EvoEvalCodegenAgent(BaseAgent):
    """One greedy chat completion per problem, as in the original EvoEval harness."""

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        max_new_tokens: int | str = 32768,
        temperature: float | str = 0.0,
        request_timeout_sec: float | str = 900.0,
        problem_deadline_sec: float | str = 36000.0,
        **kwargs: Any,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.max_new_tokens = int(max_new_tokens)
        self.temperature = float(temperature)
        self.request_timeout_sec = float(request_timeout_sec)
        self.problem_deadline_sec = float(problem_deadline_sec)

    @staticmethod
    def name() -> str:
        return "evoeval-codegen"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    def _api_model(self) -> str:
        if not self.model_name:
            raise ValueError("evoeval-codegen needs a model (-m openai/<model>)")
        # Harbor model names carry a provider prefix; the API expects the bare name.
        return self.model_name.split("/", 1)[1] if "/" in self.model_name else self.model_name

    async def _request(self, config: dict) -> Any:
        """Mirror of ``request_chatgpt_engine``: retry until a response arrives.

        Same limits as the original side: ``EVOEVAL_REQUEST_TIMEOUT=900`` there is both the
        client timeout and a ``signal.alarm`` around the whole SDK call; here it is the
        client timeout and an ``asyncio.wait_for`` around the whole call. Same openai SDK
        version (default ``max_retries=2``), same waits (BadRequest -> retry at once,
        RateLimit/APIConnection -> 5 s, anything else incl. the timeout -> 1 s), and the
        same overall deadline per problem (``EVOEVAL_PROBLEM_DEADLINE`` /
        ``problem_deadline_sec``, 36000 s), after which the sample is empty.
        """
        import openai

        client = openai.AsyncOpenAI(
            api_key=self._get_env("OPENAI_API_KEY"),
            base_url=self._get_env("OPENAI_BASE_URL"),
            timeout=self.request_timeout_sec,
        )
        attempts = 0
        started = time.monotonic()
        while True:
            if time.monotonic() - started > self.problem_deadline_sec:
                # Same as the fork's EVOEVAL_PROBLEM_DEADLINE: give up, empty sample.
                return None, attempts
            attempts += 1
            try:
                # Whole-call limit, like upstream's signal.alarm around the SDK call
                # (which includes the SDK's own retries).
                ret = await asyncio.wait_for(
                    client.chat.completions.create(**config),
                    timeout=self.request_timeout_sec,
                )
                return ret, attempts
            except openai.BadRequestError as e:
                self.logger.warning("BadRequestError: %s", e)
            except openai.RateLimitError as e:
                self.logger.warning("Rate limit exceeded. Waiting... %s", e)
                await asyncio.sleep(5)
            except openai.APIConnectionError as e:
                self.logger.warning("API connection error. Waiting... %s", e)
                await asyncio.sleep(5)
            except Exception as e:  # noqa: BLE001 - upstream retries on anything
                self.logger.warning("Unknown error. Waiting... %s", e)
                await asyncio.sleep(1)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        match = ENTRY_POINT_RE.search(instruction)
        if match is None:
            raise ValueError("Could not find the entry point in the task instruction")
        entry_point = match.group(1)

        prompt_match = PROMPT_RE.search(instruction)
        if prompt_match is None:
            raise ValueError("Could not find the problem prompt in the task instruction")
        prompt = prompt_match.group(1)

        model = self._api_model()
        message = GENERATION_TEMPLATE.format(prompt=prompt.strip())
        num_tokens = num_tokens_from_messages(message, model)
        config = create_chatgpt_config(
            message=message,
            max_tokens=num_tokens + self.max_new_tokens,
            temperature=self.temperature,
            batch_size=1,
            model=model,
        )
        (self.logs_dir / "request.json").write_text(json.dumps(config, indent=2))

        started = time.time()
        ret, attempts = await self._request(config)
        elapsed = time.time() - started

        if ret is None:  # overall deadline reached without a response
            choice = None
            raw_output = ""
        else:
            choice = ret.choices[0]
            raw_output = choice.message.content or ""
        code = sanitize(raw_output, prompt, entry_point)

        (self.logs_dir / "raw_output.txt").write_text(raw_output)
        (self.logs_dir / "sanitized_solution.py").write_text(code)
        local_solution = self.logs_dir / "solution.py"
        local_solution.write_text(code)
        await environment.exec("mkdir -p /workspace")
        await environment.upload_file(local_solution, SOLUTION_PATH)

        usage = getattr(ret, "usage", None)
        reasoning_tokens = None
        if usage is not None and getattr(usage, "completion_tokens_details", None):
            reasoning_tokens = getattr(usage.completion_tokens_details, "reasoning_tokens", None)
        meta = {
            "entry_point": entry_point,
            "response_model": getattr(ret, "model", None),
            "finish_reason": getattr(choice, "finish_reason", None),
            "deadline_reached": ret is None,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "reasoning_tokens": reasoning_tokens,
            "max_tokens": config["max_tokens"],
            "attempts": attempts,
            "elapsed_sec": round(elapsed, 2),
            "raw_output_chars": len(raw_output),
            "sanitized_chars": len(code),
        }
        (self.logs_dir / "response_meta.json").write_text(json.dumps(meta, indent=2))

        context.n_input_tokens = meta["prompt_tokens"]
        context.n_output_tokens = meta["completion_tokens"]
        context.metadata = meta
