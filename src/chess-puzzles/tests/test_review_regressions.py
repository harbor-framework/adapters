"""Regression tests for externally reviewed parity failure modes. No paid API."""
import json
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from inspect_ai.model import ModelUsage

from chess_puzzles.adapter import PARITY_IDS, ChessPuzzlesAdapter
from chess_puzzles.original import evaluate
from chess_puzzles.outcomes import IncompleteEvaluation, usage_summary
from chess_puzzles.parity import (
    collect_harbor, harbor_config, report, run_pair, start_round, verify_dataset,
)
from chess_puzzles.runtime import make_model, run_upstream
from chess_puzzles.source import prepare_source

FEN = "6k1/3R4/2N3p1/PpPp4/1P1r4/5r2/6K1/8 b - - 3 56"


def settings():
    result = json.loads(Path('parity_settings.json').read_text())
    result.update(max_output_tokens=10000, response_max_tokens=1000,
                  compaction_threshold_tokens=100000)
    return result


@pytest.mark.parametrize('side', ['original', 'harbor-worker'])
async def test_real_inspect_timeout_is_incomplete_not_zero(tmp_path, side):
    config = settings()
    config.update(model='mockllm/model', base_url=None, mock_scenario='timeout', attempt_timeout_sec=1,
                  token_count_mode='provider')
    with pytest.raises(IncompleteEvaluation):
        if side == 'original':
            await evaluate(config, [1], tmp_path)
        else:
            await run_upstream(FEN, config['model'], tmp_path, config['max_output_tokens'],
                               config['compaction_threshold_tokens'], attempt_timeout_sec=1,
                               mock_scenario='timeout')
    outcome = json.loads((tmp_path / 'outcome.json').read_text())
    assert outcome['status'] == 'incomplete'
    assert outcome['samples'][0]['status'] == 'limited'
    assert outcome['samples'][0]['limit']['type'] == 'time'
    assert outcome['samples'][0]['reward'] is None
    if side == 'original':
        assert json.loads((tmp_path / 'summary.json').read_text())['accuracy'] is None


@pytest.mark.parametrize('interrupted', [False, True])
def test_empty_or_cancelled_key_creates_nothing(tmp_path, monkeypatch, interrupted):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    def key(_):
        if interrupted:
            raise KeyboardInterrupt
        return '  '
    monkeypatch.setattr('chess_puzzles.parity.getpass.getpass', key)
    def unexpected(*args, **kwargs):
        raise AssertionError('Source preparation ran before key validation')
    monkeypatch.setattr('chess_puzzles.parity.prepare_source', unexpected)
    with pytest.raises(KeyboardInterrupt if interrupted else ValueError):
        run_pair(settings(), tmp_path / 'experiment', 'sanity', 1, True,
                 dataset=tmp_path / 'tasks')
    assert list(tmp_path.iterdir()) == []


def test_parity_default_and_variant_registry_names_are_distinct(tmp_path):
    csv = prepare_source() / 'bench/task/chess_puzzles/puzzles.csv'
    original = ChessPuzzlesAdapter(tmp_path / 'original', data_path=csv, split='parity').run()
    cli = ChessPuzzlesAdapter(tmp_path / 'cli', data_path=csv, split='parity', variant='cli').run()
    assert len(original) == len(cli) == 10
    for a, b in zip(original, cli, strict=True):
        name_a = tomllib.loads((a / 'task.toml').read_text())['task']['name']
        name_b = tomllib.loads((b / 'task.toml').read_text())['task']['name']
        assert name_a != name_b
        assert 'chess-puzzles-original__' in name_a
        assert json.loads((a / 'environment/problem.json').read_text())['variant'] == 'original'
    verify_dataset(tmp_path / 'original')
    with pytest.raises(ValueError, match='original-prompt'):
        verify_dataset(tmp_path / 'cli')


def test_timeout_margin_and_explicit_sdk_retries(tmp_path):
    config = harbor_config(settings(), tmp_path, [4], tmp_path, 'test')
    assert config['agents'][0]['override_timeout_sec'] == settings()['attempt_timeout_sec'] + 300
    assert config['agents'][0]['kwargs']['attempt_timeout_sec'] == settings()['attempt_timeout_sec']
    model = make_model('anthropic/claude-haiku-5-5', 'http://127.0.0.1:1', 'fake-test-key')
    assert model.api.model_args['max_retries'] == 2


def test_cached_usage_is_counted_without_inventing_price():
    usage = usage_summary({'test': ModelUsage(input_tokens=10, output_tokens=3,
                                             input_tokens_cache_read=20, input_tokens_cache_write=30)})
    assert usage['input_tokens'] == 60
    assert usage['uncached_input_tokens'] == 10
    assert usage['cache_read_tokens'] == 20
    assert usage['cache_write_tokens'] == 30
    assert usage['by_model']['test']['total_cost'] is None


def test_explicit_failed_round_retry_preserves_evidence(tmp_path):
    run = tmp_path / 'formal-2'
    run.mkdir()
    (run / 'failure.json').write_text('{}')
    (run / 'original.log').write_text('partial evidence')
    completed = tmp_path / 'formal-1'
    completed.mkdir()
    (completed / 'pair-complete.json').write_text('{}')
    with pytest.raises(ValueError, match='retry requires'):
        start_round(tmp_path, run, False, None)
    start_round(tmp_path, run, True, 'Provider outage confirmed in the retained logs')
    archived = list((tmp_path / 'failed-attempts').iterdir())
    assert len(archived) == 1
    assert (archived[0] / 'original.log').read_text() == 'partial evidence'
    assert (run / 'retry.json').exists()
    assert (completed / 'pair-complete.json').exists()
    with pytest.raises(ValueError, match='Completed'):
        start_round(tmp_path, completed, True, 'Do not replace results')


def test_failure_record_and_prepare_output_used(tmp_path, monkeypatch):
    config = settings()
    dataset = tmp_path / 'prepared'
    csv = prepare_source() / 'bench/task/chess_puzzles/puzzles.csv'
    ChessPuzzlesAdapter(dataset, data_path=csv, split='parity').run()
    root = tmp_path / 'experiment'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'offline-test-key')
    captured = []
    def fake_run(command, **kwargs):
        captured.append(command)
        if command[1:3] == ['-m', 'chess_puzzles.original']:
            return SimpleNamespace(returncode=0)
        harbor = json.loads(Path(command[-1]).read_text())
        assert harbor['datasets'][0]['path'] == str(dataset.resolve())
        raise subprocess.CalledProcessError(1, ['harbor'])
    monkeypatch.setattr('chess_puzzles.parity.subprocess.run', fake_run)
    with pytest.raises(subprocess.CalledProcessError):
        run_pair(config, root, 'sanity', 1, True, dataset=dataset)
    assert len(captured) == 2
    failure = json.loads((root / 'sanity-1/failure.json').read_text())
    assert failure['stage'] == 'harbor'
    assert not (root / 'tasks').exists()
    assert 'offline-test-key' not in (root / 'settings.json').read_text()
    assert not (root / 'sanity-1/pair-complete.json').exists()


def test_collect_retains_limit_and_null_reward(tmp_path):
    trial = tmp_path / 'trial'
    diagnosis = trial / 'agent/inspect'
    diagnosis.mkdir(parents=True)
    (trial / 'result.json').write_text(json.dumps({
        'task_name': 'epoch-ai/chess-puzzles-original__chess-puzzles-004',
        'exception_info': {'exception_type': 'RuntimeError'},
    }))
    (diagnosis / 'outcome.json').write_text(json.dumps({
        'status': 'incomplete', 'usage': {}, 'samples': [{
            'id': 4, 'status': 'limited', 'limit': {'type': 'time', 'limit': 1}, 'reward': None,
        }],
    }))
    with pytest.raises(RuntimeError, match='limited'):
        collect_harbor(tmp_path, [4], simulated=True)
    summary = json.loads((tmp_path / 'summary.json').read_text())
    assert summary['accuracy'] is None
    assert summary['samples'][0]['reward'] is None
    assert summary['samples'][0]['limit']['type'] == 'time'


def test_report_disagreements_and_rejects_incomplete(tmp_path):
    for n in (1, 2, 3):
        folder = tmp_path / f'formal-{n}'
        folder.mkdir()
        (folder / 'pair-complete.json').write_text('{}')
        for side in ('original', 'harbor'):
            (folder / side).mkdir()
            rows = [{'id': i, 'reward': int(i == (4 if side == 'original' else 14))} for i in PARITY_IDS]
            (folder / side / 'summary.json').write_text(json.dumps({
                'status': 'complete', 'simulated': False, 'samples': rows, 'accuracy': 0.1,
            }))
    result = report(tmp_path)
    assert result['disagreements'][0] == {
        'round': 1, 'original_only_correct': [4], 'harbor_only_correct': [14],
    }
    assert result['per_puzzle'][4]['original'] == [1, 1, 1]
    file = tmp_path / 'formal-1/original/summary.json'
    data = json.loads(file.read_text())
    data['status'] = 'incomplete'
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Incomplete'):
        report(tmp_path)


async def test_actual_upstream_compaction_path(tmp_path):
    answer, log = await run_upstream(FEN, "mockllm/model", tmp_path, 20000, 1000,
                                     mock_scenario="compact")
    assert answer == "d4d3"
    assert any((message.metadata or {}).get("summary") for message in log.samples[0].messages)
    assert log.samples[0].metadata["forced_final_answer"] is False


def test_completed_solver_with_failed_verifier_is_still_incomplete(tmp_path):
    trial = tmp_path / 'trial'
    diagnosis = trial / 'agent/inspect'
    diagnosis.mkdir(parents=True)
    (trial / 'result.json').write_text(json.dumps({
        'task_name': 'chess-puzzles-004', 'exception_info': {'exception_type': 'VerifierError'},
    }))
    (diagnosis / 'outcome.json').write_text(json.dumps({
        'status': 'complete', 'samples': [{'id': 4, 'status': 'complete', 'limit': None}],
    }))
    with pytest.raises(RuntimeError, match='failed'):
        collect_harbor(tmp_path, [4])
    summary = json.loads((tmp_path / 'summary.json').read_text())
    assert summary['accuracy'] is None
    assert summary['samples'][0]['status'] == 'error'


async def test_token_count_failure_has_no_hidden_inspect_retry(monkeypatch):
    import asyncio
    import socket
    import httpx
    from anthropic import APIStatusError
    from tenacity import RetryError
    from chess_puzzles.runtime import make_model

    def no_network(*args, **kwargs):
        raise AssertionError('Offline retry test attempted a network connection')
    monkeypatch.setattr(socket.socket, 'connect', no_network)
    model = make_model('anthropic/claude-haiku-5-5', 'http://127.0.0.1:1', 'offline-retry-test')
    assert model.config.max_retries == 0
    assert model.api.client.max_retries == 2
    calls = 0
    async def unavailable(*args, **kwargs):
        nonlocal calls
        calls += 1
        response = httpx.Response(503, request=httpx.Request('POST', 'http://127.0.0.1:1/v1/messages/count_tokens'))
        raise APIStatusError('offline simulated 503', response=response, body={'error': 'unavailable'})
    monkeypatch.setattr(model.api, 'count_tokens', unavailable)
    async with model:
        with pytest.raises(RetryError) as failure:
            await asyncio.wait_for(model.count_tokens('offline check'), timeout=2)
        assert isinstance(failure.value.last_attempt.exception(), APIStatusError)
    assert calls == 1
