"""Run the proposed GSM8K paired prompt and preserve each raw completion."""

import argparse
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
from urllib.request import Request, urlopen

from harbor.agents.base import BaseAgent

from .adapter import ANSWER_PATH, WRAPPER, read_source, select_examples
from .reference import load_reference


def load_profile(path):
    profile = json.loads(Path(path).read_bytes())
    required = {"model", "temperature", "max_completion_tokens", "timeout_seconds"}
    if profile.keys() != required or not isinstance(profile["model"], str) or not profile["model"]:
        raise ValueError("Supply the exact model, temperature, output budget and timeout")
    return profile


def request_payload(question, profile):
    prompt = question + "\n\nSolve the problem. End with a line in the format #### NUMBER."
    return {key: value for key, value in profile.items() if key != "timeout_seconds"} | {
        "messages": [{"role": "user", "content": prompt}],
    }


def complete(question, profile):
    data = json.dumps(request_payload(question, profile), sort_keys=True).encode()
    request = Request(
        os.environ["GSM8K_PARITY_BASE_URL"].rstrip("/") + "/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["GSM8K_PARITY_API_KEY"]},
    )
    with urlopen(request, timeout=profile["timeout_seconds"]) as response:
        result = json.load(response)
    choice, = result["choices"]
    if result["model"] != profile["model"]:
        raise ValueError("The endpoint returned a different model revision")
    message = choice["message"]
    content = message["content"]
    if content is None and message.get("refusal"):
        content = ""
    if not isinstance(content, str):
        raise ValueError("The endpoint did not return a text completion")
    return {"completion": content, "model": result["model"], "finish_reason": choice["finish_reason"],
            "usage": result.get("usage"), "request_sha256": sha256(data).hexdigest()}


class PairedParityAgent(BaseAgent):
    def __init__(self, *, profile_path, scorer_path, **kwargs):
        super().__init__(**kwargs)
        self.profile = load_profile(profile_path)
        self.extract, _ = load_reference(Path(scorer_path))

    @staticmethod
    def name():
        return "gsm8k-paired-chat"

    def version(self):
        return "0.1.0"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        if not instruction.endswith(WRAPPER):
            raise ValueError("GSM8K instruction differs from the fixed file protocol")
        question = instruction.removesuffix(WRAPPER)
        record = await asyncio.to_thread(complete, question, self.profile)
        (self.logs_dir / "completion.json").write_text(json.dumps(record, ensure_ascii=False) + "\n")
        answer = shlex.quote(self.extract(record["completion"]))
        result = await environment.exec(
            command="test \"$(id -u)\" -eq 1001 && test ! -e /tests/gold.txt && test ! -e /solution/solve.sh "
                    f"&& test ! -e {ANSWER_PATH} && printf '%s' {answer} > {ANSWER_PATH}",
        )
        if result.return_code != 0:
            raise RuntimeError("Unable to write a fresh answer in the non-root agent environment")


def original_side(args):
    examples = read_source(args.source.read_bytes())
    task_ids = args.task_ids.split(",") if args.task_ids else ()
    profile = load_profile(args.profile)
    _, is_correct = load_reference(args.scorer)
    with args.output.open("x", encoding="utf-8") as output:
        for example in select_examples(examples, task_ids):
            record = complete(example.question, profile)
            record.update(task_name=example.task_name, source_line_sha256=example.line_sha256,
                          reward=int(is_correct(record["completion"], {"answer": example.upstream_answer})))
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "scorer", "profile", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--task-ids", help="Comma-separated pinned test IDs. Defaults to the full test split.")
    original_side(parser.parse_args())


if __name__ == "__main__":
    main()
