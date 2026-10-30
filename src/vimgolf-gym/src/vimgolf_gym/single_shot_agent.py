"""Parity agent reproducing vimgolf-gym's ``vimgolf-benchmark.py --runner single_shot``.

It sends the upstream prompt verbatim as a single system message through litellm
(streaming, provider defaults, like upstream), takes the last non-empty line of the
response (reasoning wrapped in <thinking> tags, as upstream records it) and writes it
to /app/solution.txt. Run with:

    harbor run -p datasets/vimgolf-gym \
        -a vimgolf_gym.single_shot_agent:VimGolfSingleShotAgent -m <litellm model>
"""

from __future__ import annotations

import base64
import json
import shlex

import litellm

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

CHALLENGE_PATH = "/app/challenge.json"
SOLUTION_PATH = "/app/solution.txt"


def build_prompt(details: str, input_content: str, output_content: str) -> str:
    # Verbatim from vimgolf-benchmark.py::run_single_shot, including its typos and the
    # two-space "blank" lines (string-compared against upstream).
    return f"""
Vimgolf is a game where you try to transform text using the fewest number of keystrokes in Vim.

Your task is to solve the following Vimgolf challenge with details:
  
Details:
  
{details}

The input file wrapped in triple backticks:
  
```
{input_content}
```

The output file wrapped in triple backticks:
  
```
{output_content}
```

Your keystokes must be less than the length of output file. Do not naively copy and paste the output file. You must use Vim commands to transform the input file into the output file.

Here are some example solutions, for format demostration (all solutions shall be in one line):

iHello World<Esc>:wq<NL>

:%s/abcdef/defabc/g<NL>:wq<NL>

Your last line of response will be treated as solution. Do not wrap the solution around any marker (like triple backticks), just write it in plain style. Do not write it in multiline style. Do not write any comment or explanation. Do not write any other text. Just write the solution. If your solution contains multiple steps, you will concatenate these steps into one line, optionally using <NL> as separator, depending on the situation.

Example response:

I think the following solution is optimal:

iHello World<Esc>:s/World/Earth/g<NL>:wq<NL>

Please write your solution according to the rules and the example response:
"""


def get_last_non_empty_line(content: str) -> str:
    lines = [it.strip() for it in content.splitlines() if it.strip()]
    return lines[-1] if lines else ""


class VimGolfSingleShotAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "vimgolf-single-shot"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def _complete(self, prompt: str) -> tuple[str, dict]:
        """Mirror of vimgolf-benchmark.py LLM.acompletion."""
        response = await litellm.acompletion(
            self.model_name,
            messages=[{"role": "system", "content": prompt}],
            stream=True,
        )
        full_response: list[str] = []
        thinking = False
        usage: dict = {}
        async for chunk in response:
            if getattr(chunk, "usage", None):
                usage = dict(chunk.usage)
            if not chunk.choices:
                continue
            delta = chunk.choices[0]["delta"]
            # Upstream does not reset chunk_content per chunk, so a final chunk whose
            # delta has neither field re-appends the previous chunk. Fixed here and in
            # the parity fork of vimgolf-gym (see README "Notes & Caveats").
            chunk_content = None
            if delta.get("reasoning_content") is not None:
                chunk_content = delta["reasoning_content"]
                if not thinking:
                    full_response.append("<thinking>\n")
                    thinking = True
            elif delta.get("content") is not None:
                chunk_content = delta["content"]
                if thinking:
                    full_response.append("</thinking>\n")
                    thinking = False
            if chunk_content:
                full_response.append(chunk_content)
        return "".join(full_response), usage

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self.model_name:
            raise RuntimeError("model_name is required for VimGolfSingleShotAgent")
        result = await environment.exec(command=f"cat {CHALLENGE_PATH}")
        if result.return_code != 0 or not result.stdout:
            raise RuntimeError(f"cannot read {CHALLENGE_PATH}: {result.stderr}")
        challenge = json.loads(result.stdout)

        # vimgolf-benchmark.py build_vimgolf_public_task: description = metadata detail,
        # input/output = raw challenge data
        prompt = build_prompt(challenge["detail"], challenge["input"], challenge["output"])
        response_text, usage = await self._complete(prompt)
        solution = get_last_non_empty_line(response_text) if response_text else ""

        (self.logs_dir / "prompt.txt").write_text(prompt)
        (self.logs_dir / "response.txt").write_text(response_text)
        (self.logs_dir / "solution.txt").write_text(solution)

        encoded = base64.b64encode(solution.encode("utf-8")).decode("ascii")
        await environment.exec(
            command=f"printf %s {shlex.quote(encoded)} | base64 -d > {SOLUTION_PATH}"
        )

        context.n_input_tokens = usage.get("prompt_tokens") or 0
        context.n_output_tokens = usage.get("completion_tokens") or 0
