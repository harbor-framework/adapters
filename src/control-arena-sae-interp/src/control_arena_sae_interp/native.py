"""Run one text-only SAE sample through ControlArena's native trusted monitor."""

import argparse
import json
import runpy
from pathlib import Path

from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.scorers import max_suspicion_scorer
from control_arena.settings.sae_interp_sabotage.scorers import (
    ResponseType,
    sae_interp_scorer,
)
from control_arena.settings.sae_interp_sabotage.setting import SAEInterpSetting
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai import eval, task_with
from inspect_ai.model import Model, ModelOutput, ModelUsage, get_model

from .adapter import TEMPLATE, instruction_for

FIXTURE = "mockllm/sae-fixture"


def fixture_actor(role: str) -> Model:
    """Supply a scripted model response, retaining native policy and monitor logic."""
    model_name = f"{FIXTURE}-{role}"
    if role == "policy":
        output = ModelOutput.for_tool_call(
            model_name,
            "submit",
            {"interpretation": "A synthetic theme used to test submission transport."},
        )
    else:
        output = ModelOutput.from_content(
            model_name, "<reason>Scripted monitor fixture.</reason><score>2</score>"
        )
    output.usage = ModelUsage()
    return get_model(model_name, custom_outputs=[output], memoize=False)


def run_sample(
    source_index: int,
    mode: EvalMode,
    model: str,
    trusted_model: str,
    judge_model: str | None,
    log_dir: Path,
) -> dict:
    """Leave the Inspect log intact; return the native submission and raw scores."""
    setting = SAEInterpSetting(scorer_model=judge_model)
    dataset = setting.get_dataset(mode)
    if not 0 <= source_index < len(dataset):
        raise ValueError(f"SAE source index outside dataset: {source_index}")

    policy = fixture_actor("policy") if model == FIXTURE else model
    monitor = fixture_actor("monitor") if trusted_model == FIXTURE else trusted_model
    config = ControlEvalConfig(
        untrusted_model=policy,
        trusted_model=monitor,
        skip_task_scorers=judge_model is None,
    )
    task = get_control_task(
        setting=setting,
        micro_protocol=trusted_monitoring_builder(),
        mode=mode,
        eval_config=config,
        dataset=[dataset[source_index]],
        monitoring_scorers=[max_suspicion_scorer()],
        metadata={"source_index": source_index},
    )
    if judge_model == FIXTURE:
        fixture_judge = runpy.run_path(str(TEMPLATE / "tests" / "fixture_judge.py"))[
            "fixture_judge"
        ]
        task = task_with(
            task, scorer=[sae_interp_scorer(fixture_judge()), max_suspicion_scorer()]
        )
    (log,) = eval(
        task,
        model=policy,
        log_dir=str(log_dir),
        display="none",
        ctl_server=False,
        fail_on_error=True,
        log_samples=True,
    )
    if log.status != "success":
        raise RuntimeError(log.error.message if log.error else f"Inspect status: {log.status}")
    (sample,) = log.samples or []
    if sample.error:
        raise RuntimeError(sample.error.message)
    stored = sample.store.get(STORE_SUBMIT_ARGS_KEY)
    submission = ResponseType.model_validate_json(stored) if stored is not None else None
    return {
        "source_index": source_index,
        "mode": mode.value,
        "submission": submission.model_dump() if submission else None,
        "scores": {name: score.value for name, score in (sample.scores or {}).items()},
        "model_usage": {
            name: usage.model_dump() for name, usage in sample.model_usage.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-index", type=int, help="Zero-based ControlArena source row")
    source.add_argument("--instruction-file", type=Path, help="Generated Harbor prompt to match")
    parser.add_argument("--mode", choices=[m.value for m in EvalMode], default="honest")
    parser.add_argument("--model", required=True, help="Inspect policy model")
    parser.add_argument("--trusted-model", required=True, help="Inspect monitor model")
    grading = parser.add_mutually_exclusive_group(required=True)
    grading.add_argument("--judge-model", help="Inspect model for the native task scorer")
    grading.add_argument(
        "--verifier-grades", action="store_true", help="Delegate task grading to Harbor"
    )
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument(
        "--result-file", type=Path, help="Write machine-readable results to this file"
    )
    args = parser.parse_args()
    mode = EvalMode(args.mode)
    index = args.source_index
    if args.instruction_file:
        instruction = args.instruction_file.read_text(encoding="utf-8")
        matches = [
            i for i, sample in enumerate(SAEInterpSetting().get_dataset(mode))
            if instruction_for(sample) == instruction
        ]
        if len(matches) != 1:
            parser.error(f"Expected exactly one matching SAE instruction; found {len(matches)}")
        index = matches[0]
    result = run_sample(index, mode, args.model, args.trusted_model, args.judge_model, args.log_dir)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.result_file:
        args.result_file.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
