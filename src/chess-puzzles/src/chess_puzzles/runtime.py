"""Run the actual pinned upstream solver, with no terminal or chess engine tool."""

from inspect_ai import eval_async
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import GenerateConfig, get_model
from pathlib import Path

from .source import upstream
from .outcomes import evaluation_outcome, require_complete
from .token_counting import configure_token_counting, validate_count_mode

# SDK retries HTTP requests; Inspect and Harbor do not retry whole samples.
HTTP_MAX_RETRIES = 2


async def run_upstream(
    fen,
    model,
    log_dir,
    max_output_tokens,
    compaction_threshold_tokens,
    source_dir=None,
    base_url=None,
    api_key=None,
    reasoning_effort=None,
    response_max_tokens=None,
    attempt_timeout_sec=1800,
    sample_id=1,
    mock_scenario=None,
    token_count_mode="provider",
):
    original = upstream(source_dir)
    task = original.chess_puzzles(
        max_output_tokens=max_output_tokens,
        compaction_threshold_tokens=compaction_threshold_tokens,
    )
    # Neither the gold target nor the full dataset is sent to the model.
    task.dataset = MemoryDataset([Sample(input=fen, target="", id=sample_id)])
    kwargs = generation_kwargs(model, reasoning_effort, response_max_tokens)
    model = make_model(model, base_url, api_key, mock_scenario,
                       token_count_mode=token_count_mode,
                       count_audit_path=Path(log_dir) / "token-counts.jsonl")
    logs = await eval_async(
        task,
        model=model,
        log_dir=str(log_dir),
        score=False,
        max_samples=1,
        fail_on_error=True,
        retry_on_error=0,
        max_retries=0,
        time_limit=attempt_timeout_sec,
        **kwargs,
    )
    if len(logs) != 1:
        raise RuntimeError("Upstream evaluation returned no unique log")
    require_complete(evaluation_outcome(logs[0], [sample_id], log_dir, token_count_mode))
    sample = logs[0].samples[0]
    return sample.output.completion, logs[0]


def make_model(model, base_url=None, api_key=None, mock_scenario=None, *,
               token_count_mode="provider", count_audit_path=None):
    validate_count_mode(token_count_mode)
    if mock_scenario is not None:
        if token_count_mode != "provider":
            raise ValueError("Use a mocked Anthropic provider to test local counting")
        if not isinstance(model, str) or not model.startswith("mockllm/"):
            raise ValueError("Simulated responses may only be used with mockllm")
        from .simulation import outputs
        return get_model(model, config=GenerateConfig(max_retries=0),
                         custom_outputs=outputs(mock_scenario), memoize=False)
    if not isinstance(model, str):
        return configure_token_counting(model, token_count_mode, count_audit_path)
    kwargs = {"max_retries": HTTP_MAX_RETRIES} if model.startswith("anthropic/") else {}
    # count_tokens() and compact() read the model instance's config, not only
    # the eval_async overrides. Without this they can retry indefinitely.
    instance = get_model(model, base_url=base_url, api_key=api_key,
                         config=GenerateConfig(max_retries=0), memoize=False, **kwargs)
    return configure_token_counting(instance, token_count_mode, count_audit_path)


def generation_kwargs(model, reasoning_effort, response_max_tokens):
    if model == "anthropic/claude-haiku-5-5" and reasoning_effort is not None:
        raise ValueError("Pinned Inspect drops forced tool choice with explicit Haiku reasoning_effort; retain model default until a symmetric fix is verified")
    kwargs = {} if reasoning_effort is None else {"reasoning_effort": reasoning_effort}
    if response_max_tokens is not None:
        kwargs["max_tokens"] = response_max_tokens
    return kwargs
