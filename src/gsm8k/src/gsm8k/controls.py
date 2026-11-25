"""A model-free Harbor agent for replaying predeclared answer bytes."""

from hashlib import sha256
import json
from pathlib import Path
import shlex

from harbor.agents.base import BaseAgent


class AnswerReplayAgent(BaseAgent):
    def __init__(self, *, answers_path, **kwargs):
        super().__init__(**kwargs)
        self.answers = json.loads(Path(answers_path).read_text())

    @staticmethod
    def name():
        return "gsm8k-answer-replay"

    def version(self):
        return "1.0.0"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        key = sha256(instruction.encode()).hexdigest()
        answer = shlex.quote(self.answers[key])
        result = await environment.exec(
            command="test \"$(id -u)\" -eq 1001 && test ! -e /tests/gold.txt && test ! -e /solution/solve.sh "
                    "&& test ! -e /app/output/answer.txt "
                    f"&& printf '%s' {answer} > /app/output/answer.txt",
        )
        if result.return_code != 0:
            raise RuntimeError("Replay requires the non-root agent, a fresh output path, and private grader files")
