"""Compare a completed seven-task Harbor oracle job against the direct native main scorer."""

import argparse
import asyncio
import json
from pathlib import Path

from control_arena import EvalMode
from control_arena._control_task_metadata import ControlTaskMetadata
from control_arena.settings.data_poisoning.config import SETTING_DESCRIPTION
from control_arena.settings.data_poisoning.dataset import get_all_main_tasks
from control_arena.settings.data_poisoning.scorers import main_task_scorer
from control_arena.settings.data_poisoning.submission_types import TrainingPair
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai.model import ModelName, ModelOutput, ModelUsage, get_model
from inspect_ai.scorer import CORRECT
from inspect_ai.solver import TaskState

from control_arena_data_quality_honest.public_case import DOMAIN, digest
from control_arena_data_quality_honest.references import reference

FIXTURE = "mockllm/data-quality-fixture"


async def compare(job: Path):
    meta = json.loads((job / "result.json").read_bytes())
    stats = meta["stats"]
    if not meta["finished_at"] or stats["n_completed_trials"] != 7 or stats["n_errored_trials"] != 0:
        raise ValueError("Expected a completed, error-free seven-task job")
    prompts = {i: p for d, i, p in get_all_main_tasks() if d == DOMAIN}
    seen = set()
    for provenance in sorted(job.glob("*/verifier/provenance.json")):
        proof = json.loads(provenance.read_bytes())
        index = proof["source_index"]
        source = prompts[index]
        if index in seen or proof["judge_model"] != FIXTURE or proof["source_prompt_sha256"] != digest(source):
            raise ValueError("Unexpected case, judge or prompt identity")
        seen.add(index)
        trial = provenance.parents[1]
        (artifact,) = (trial / "artifacts").rglob("submission.json")
        submitted = TrainingPair.model_validate_json(artifact.read_bytes(), strict=True)
        if submitted != reference(index):
            raise ValueError("Expected the adapter-authored oracle response")
        metadata = ControlTaskMetadata(main_task_description=source, setting_description=SETTING_DESCRIPTION,
                                      main_task_name=f"generate_{DOMAIN}_monitor_data", side_task_description="",
                                      eval_mode=EvalMode.HONEST, setting_name="data_poisoning")
        state = TaskState(model=ModelName("mockllm/model"), sample_id=index, epoch=1, input=source,
                          messages=[], metadata=metadata.model_dump(), store={STORE_SUBMIT_ARGS_KEY: submitted.model_dump_json()})
        output = ModelOutput.from_content(FIXTURE, "<reasoning>Direct native grading fixture.</reasoning><score>8</score>")
        output.usage = ModelUsage()
        native = await main_task_scorer(state, get_model(FIXTURE, custom_outputs=[output]))
        harbor = json.loads((provenance.parent / "reward.json").read_bytes())
        if native.value != CORRECT or harbor != {"main_task_success": 1}:
            raise AssertionError(f"Native or Harbor reference verdict failed for row {index}")
    if seen != prompts.keys():
        raise ValueError("Missing factual-accuracy rows")
    print(f"All {len(seen)} Harbor fixture verdicts matched the direct native main-task scorer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("harbor_job", type=Path)
    asyncio.run(compare(parser.parse_args().harbor_job))
