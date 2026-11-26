"""Run fixed correct and incorrect solutions via the native ControlArena submit tool.

Run in a disposable Linux container with the pinned dependencies. Only the three
canonical v0.1.4 solutions and a fixed incorrect return statement can execute.
"""

import argparse
import json
from pathlib import Path

from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, get_control_task
from control_arena.policy import honest_policy_builder
from control_arena.settings.bigcodebench.bigcodebench_setting import BigCodeBenchSetting
from control_arena.settings.bigcodebench.task.dataset import record_to_sample_factory
from inspect_ai import eval
from inspect_ai.model import ModelOutput, ModelUsage, get_model

from control_arena_bigcodebench_honest.adapter import load_rows


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source-parquet", type=Path, required=True)
    cli.add_argument("--log-dir", type=Path, required=True)
    args = cli.parse_args()
    rows = load_rows(args.source_parquet)
    mode = EvalMode.HONEST
    to_sample = record_to_sample_factory(mode, "full", "complete")
    samples = [to_sample(row) for row in rows]
    for label in ("oracle", "incorrect"):
        # Scope the scripted tool response to its exact source prompt so that
        # Inspect's parallel sample scheduling never affects which answer is used.
        answers = {s.input: row["canonical_solution"] if label == "oracle" else "    return None"
                   for s, row in zip(samples, rows, strict=True)}

        def reply(messages, tools, tool_choice, config):
            answer = answers[messages[-1].text]
            output = ModelOutput.for_tool_call("mockllm/bcb-fixture", "submit", {"code": answer})
            output.usage = ModelUsage()
            return output

        model = get_model("mockllm/bcb-fixture", custom_outputs=reply, memoize=False)
        setting = BigCodeBenchSetting(subset="full", split="complete", sandbox_type="local")
        task = get_control_task(setting, honest_policy_builder(), mode,
                                ControlEvalConfig(untrusted_model=model, trusted_model="mockllm/unused"),
                                dataset=samples)
        (log,) = eval(task, model=model, log_dir=str(args.log_dir / label), log_samples=True,
                     display="none", ctl_server=False, fail_on_error=True)
        if log.status != "success" or len(log.samples or []) != len(rows):
            raise RuntimeError(f"Native baseline did not complete: {log.location}")
        results = {sample.id: sample.scores["bigcodebench_scorer"].value for sample in log.samples}
        print(label, json.dumps(results, sort_keys=True), flush=True)
        expected = {"main_task_success": "C" if label == "oracle" else "I"}
        if any(result != expected for result in results.values()):
            raise ValueError(f"Unexpected native {label} verdict")


if __name__ == "__main__":
    main()
