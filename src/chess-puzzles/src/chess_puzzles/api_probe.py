"""Small Anthropic transport check, separate from benchmark and parity scores."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model
from inspect_ai.tool import ToolDef, ToolFunction, ToolInfo, tool_with

from .source import upstream
from .token_counting import configure_token_counting, count_settings


def submission_tool(source_dir):
    original = upstream(source_dir)
    from bench.solver.submission import submit_answer
    definition = ToolDef(tool_with(submit_answer(), description=original.SUBMIT_DESCRIPTION))
    return ToolInfo(name=definition.name, description=definition.description,
                    parameters=definition.parameters)


async def probe(settings, api_key, destination):
    """Three fresh conversations; no chess scoring, continuation or compaction claims."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    report_path = destination / 'result.json'
    result = {
        'kind': 'api_compatibility_only', 'status': 'incomplete',
        'model': settings['model'], 'base_url': settings['base_url'],
        'counts_as_parity': False, 'sdk_retries': 0,
        'requested_output_token_caps': [64, 256, 256], 'checks': [],
        'not_covered': ['upstream qa_agent loop', 'multi-turn thinking replay', 'context compaction'],
        'token_counting': count_settings(settings.get('token_count_mode', 'provider')),
    }
    stage = 'source'
    try:
        tool = submission_tool(settings.get('source_dir'))
        messages = [ChatMessageUser(content=(
            'This is an API connectivity check, not a chess puzzle. '
            'Call submit_answer with the string b1c3. Do not analyze a chess position.'
        ))]
        for stage, streaming, choice, cap in (
            ('automatic_streaming', True, 'auto', 64),
            ('forced_nonstreaming', False, ToolFunction('submit_answer'), 256),
            ('forced_streaming', True, ToolFunction('submit_answer'), 256),
        ):
            async with get_model(settings['model'], base_url=settings['base_url'],
                                 api_key=api_key, streaming=streaming, max_retries=0,
                                 memoize=False) as model:
                mode = settings.get('token_count_mode', 'provider')
                configure_token_counting(model, mode, destination / 'token-counts.jsonl')
                if mode == 'local' and 'provider count_tokens endpoint' not in result['not_covered']:
                    result['not_covered'].append('provider count_tokens endpoint')
                async with asyncio.timeout(180):
                    if stage == 'automatic_streaming':
                        count = await model.api.count_tokens(messages)
                        if not isinstance(count, int) or count < 1:
                            raise RuntimeError('Invalid count_tokens response')
                        result['checks'].append({'check': 'local_token_estimate' if mode == 'local' else 'provider_count_tokens', 'status': 'passed',
                                                 'input_tokens': count})
                    # Direct provider call deliberately sends forced tool_choice instead
                    # of assuming a small max_tokens will make qa_agent force an answer.
                    returned = await model.api.generate(
                        messages, [tool], choice, GenerateConfig(max_tokens=cap, max_retries=0)
                    )
                    output = returned[0] if isinstance(returned, tuple) else returned
                    calls = output.message.tool_calls or []
                    row = {'check': stage, 'streaming': streaming, 'max_tokens': cap,
                           'stop_reason': output.stop_reason,
                           'output': output.model_dump(mode='json'), 'status': 'passed'}
                    result['checks'].append(row)
                    if choice != 'auto' and (
                        output.stop_reason == 'max_tokens'
                        or not any(call.function == 'submit_answer' and not call.parse_error
                                   and call.arguments.get('answer') == 'b1c3' for call in calls)
                    ):
                        row['status'] = 'failed'
                        raise RuntimeError('Forced request did not return the requested complete tool call')
        result['status'] = 'complete'
    except (Exception, KeyboardInterrupt, asyncio.CancelledError) as error:
        result['failed_stage'] = stage
        # Error bodies can echo request headers. Store type/status, never a raw body.
        result['error_type'] = type(error).__name__
        result['http_status'] = getattr(error, 'status_code', None)
        raise
    finally:
        report_path.write_text(json.dumps(result, indent=2) + '\n')
    return result


def run_probe(settings, root, execute, get_key):
    if not execute:
        print(f"Plan only: {settings.get('token_count_mode', 'provider')} counting check plus 3 small requests (64/256/256 output caps). Add --execute to use the API.")
        return
    if settings['model'] != 'anthropic/claude-haiku-5-5':
        raise ValueError('This compatibility probe is for the configured Haiku 5.5 model')
    key = get_key()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = root / ('api-probe-' + stamp)
    try:
        asyncio.run(probe(settings, key, destination))
    except Exception as error:
        status = getattr(error, 'status_code', None)
        detail = f'HTTP {status}' if status else type(error).__name__
        raise RuntimeError(f'API check failed ({detail}); see {destination / "result.json"}') from None
    print(f'API check complete. This is not a parity result. Details: {destination / "result.json"}')
