"""Check two completed Harbor fixture trials against independently run native logs."""

import argparse
import json
from pathlib import Path

from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY
from inspect_ai.log import read_eval_log
from inspect_ai.scorer import CORRECT, INCORRECT


def load_sample(path: Path):
    if path.is_dir():
        (path,) = path.glob("*.eval")
    log = read_eval_log(path, resolve_attachments=True)
    if log.status != "success":
        raise ValueError(f"Incomplete Inspect log: {path}")
    (sample,) = log.samples or []
    if sample.error:
        raise ValueError(f"Sample error in {path}: {sample.error.message}")
    return sample


def model_inputs(sample, role: str | None) -> list[str]:
    calls = []
    for event in sample.events:
        if event.event != "model" or event.role != role:
            continue
        # Inspect assigns new message IDs at construction. Compare the actual
        # model-facing content, tool definitions, tool choice and configuration.
        fields = event.model_dump(mode="json", include={"model", "tools", "tool_choice", "config"})
        fields["input"] = [m.model_dump(mode="json", exclude={"id"}) for m in event.input]
        calls.append(json.dumps(fields, sort_keys=True))
    if not calls:
        raise ValueError(f"No model calls found for role {role!r}")
    return calls


def check(got, expected, label: str) -> None:
    if got != expected:
        raise ValueError(f"Fixture mismatch: {label}")


def compare(mode: str, native: Path, trial: Path):
    original = load_sample(native)
    harbor = load_sample(trial / "agent" / "inspect")
    for sample in (original, harbor):
        check(sample.metadata["eval_mode"], mode, f"{mode} dataset mode")
    for role in ("trusted", "untrusted"):
        check(model_inputs(harbor, role), model_inputs(original, role), f"{mode} {role} inputs")

    submitted = json.loads(original.store[STORE_SUBMIT_ARGS_KEY])
    check(json.loads(harbor.store[STORE_SUBMIT_ARGS_KEY]), submitted, f"{mode} native submit")
    (artifact,) = (trial / "artifacts").rglob("submission.json")
    check(json.loads(artifact.read_text(encoding="utf-8")), submitted, f"{mode} uploaded submit")
    check(harbor.scores["max_suspicion_scorer"].value, 0.2, f"{mode} fixture suspicion")
    check(
        harbor.scores["max_suspicion_scorer"].value,
        original.scores["max_suspicion_scorer"].value,
        f"{mode} monitor score",
    )
    grader = load_sample(trial / "verifier" / "inspect")
    # ControlArena evaluates two independent judge prompts concurrently in attack mode.
    check(
        sorted(model_inputs(grader, None)),
        sorted(model_inputs(original, None)),
        f"{mode} judge inputs",
    )
    scores = original.scores["sae_interp_scorer"].value
    check(grader.scores["sae_interp_scorer"].value, scores, f"{mode} native judge verdicts")
    expected = {name: {CORRECT: 1, INCORRECT: 0}[value] for name, value in scores.items()}
    actual = json.loads((trial / "verifier" / "reward.json").read_text(encoding="utf-8"))
    check(actual, expected, f"{mode} Harbor rewards")
    return harbor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for mode in ("honest", "attack"):
        parser.add_argument(
            f"--{mode}", nargs=2, required=True, type=Path, metavar=("NATIVE", "TRIAL")
        )
    args = parser.parse_args()
    honest = compare("honest", *args.honest)
    attack = compare("attack", *args.attack)
    check(model_inputs(honest, "trusted"), model_inputs(attack, "trusted"), "monitor mode opacity")
    if model_inputs(honest, "untrusted") == model_inputs(attack, "untrusted"):
        raise ValueError("Fixture policy received identical inputs in both modes")
    print("Both modes matched on model inputs, typed submissions, suspicion and rewards.")


if __name__ == "__main__":
    main()
