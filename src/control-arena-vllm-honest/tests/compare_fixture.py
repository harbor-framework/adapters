"""Replay the reference artifact with the pinned vllm_scorer and compare native judge inputs."""
import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from control_arena import EvalMode
from control_arena._control_task_metadata import ControlTaskMetadata
from control_arena.settings.vllm.task.scorers import vllm_scorer
from git import Repo
from inspect_ai.event import ModelEvent
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelName, ModelOutput, ModelUsage, get_model
from inspect_ai.scorer import CORRECT, Target
from inspect_ai.solver import TaskState

from control_arena_vllm_honest import sources

FIXTURE = "mockllm/vllm-metrics-fixture"


async def compare(job, cache):
    row = sources.materialize(cache)
    result = json.loads((job / "result.json").read_bytes())
    if not result["finished_at"] or (result["stats"]["n_completed_trials"], result["stats"]["n_errored_trials"]) != (1, 0):
        raise ValueError("Expected a complete single-trial oracle job")
    (proof_file,) = job.glob("*/verifier/provenance.json")
    proof = json.loads(proof_file.read_bytes())
    if proof["judge_model"] != FIXTURE or proof["candidate_sha256"] != sources.GOLD_SHA or proof["eval_mode"] != "honest":
        raise ValueError("Expected the honest upstream reference fixture")
    (artifact,) = (proof_file.parents[1] / "artifacts").rglob("loggers.py")
    candidate = artifact.read_bytes()
    if sources.digest(candidate) != sources.GOLD_SHA:
        raise ValueError("Unexpected collected reference")
    with TemporaryDirectory() as tmp:
        repo = Repo.init(tmp)
        path = Path(tmp) / sources.SOURCE
        path.parent.mkdir(parents=True)
        path.write_bytes((cache / "baseline.py").read_bytes())
        repo.git.add("--all")
        before = repo.git.write_tree()
        path.write_bytes(candidate)
        repo.git.add("--all")
        diff = repo.git(c="core.fileMode=false").diff(before, "--cached")
    if sources.digest(diff.encode()) != proof["diff_sha256"]:
        raise ValueError("Harbor diff differs from the native Git command")
    metadata = ControlTaskMetadata(main_task_name=sources.TITLE, main_task_description=row["task_instructions"],
                                  side_task_description="", setting_description="vLLM metrics maintenance",
                                  eval_mode=EvalMode.HONEST, setting_name="vllm", metadata={"git_code_ref": sources.BASE})
    state = TaskState(model=ModelName("mockllm/model"), sample_id=sources.TITLE, epoch=1, input=row["task_instructions"],
                      messages=[], metadata=metadata.model_dump(), store={"submission_diff": diff})
    native_prompts = []

    def respond(messages, tools, tool_choice, config):
        native_prompts.append(messages[0].text)
        output = ModelOutput.from_content(FIXTURE, "<reasoning>Direct native fixture.</reasoning><grade>accept</grade>")
        output.usage = ModelUsage()
        return output

    grade = await vllm_scorer(get_model(FIXTURE, custom_outputs=respond))(state, Target(""))
    (log_file,) = (proof_file.parent / "inspect").glob("*.eval")
    (sample,) = read_eval_log(log_file, resolve_attachments=True).samples
    harbor_prompts = [event.input[0].text for event in sample.events if isinstance(event, ModelEvent)]
    harbor_reward = json.loads((proof_file.parent / "reward.json").read_bytes())
    if not native_prompts or native_prompts != harbor_prompts:
        raise AssertionError("Native and Harbor judge inputs differ")
    if grade.value != {"main_task_success": CORRECT} or harbor_reward != {"main_task_success": 1}:
        raise AssertionError("Native and Harbor reference verdicts differ")
    print("Matched native and Harbor Git diff, PR judge input and positive reference verdict.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--source-cache", type=Path, default=Path(".cache/control-arena-vllm-honest"))
    args = parser.parse_args()
    asyncio.run(compare(args.job, args.source_cache))
