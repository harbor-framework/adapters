import json
import random
from pathlib import Path

import pytest

from chess_puzzles.adapter import PARITY_IDS, QUESTION_TEMPLATE, ChessPuzzlesAdapter
from chess_puzzles.parity import collect_harbor, harbor_config, mean_sem, validate_settings
from chess_puzzles.source import prepare_source


def test_sampling_is_the_predeclared_seed():
    assert sorted(random.Random(42).sample(range(1, 101), 10)) == list(PARITY_IDS)


def test_original_tasks_keep_exact_prompt_and_hide_targets(tmp_path):
    csv = prepare_source() / 'bench/task/chess_puzzles/puzzles.csv'
    tasks = ChessPuzzlesAdapter(tmp_path, data_path=csv, variant='original', split='parity').run()
    assert len(tasks) == 10
    for task in tasks:
        record = json.loads((task / 'tests/record.json').read_text())
        problem = json.loads((task / 'environment/problem.json').read_text())
        assert problem == {'id': record['id'], 'fen': record['fen'], 'variant': 'original'}
        assert (task / 'instruction.md').read_text() == QUESTION_TEMPLATE.format(prompt=record['fen'])
        assert 'target' not in problem
        assert 'network_mode: none' in (task / 'environment/docker-compose.yaml').read_text()
    with pytest.raises(ValueError, match='variant'):
        ChessPuzzlesAdapter(tmp_path, data_path=csv, variant='cli', split='parity', overwrite=True).run()


def test_sem_uses_run_scores_not_task_scores():
    assert mean_sem([0.4, 0.5, 0.6]) == pytest.approx({'mean': 0.5, 'sample_sem': 0.05773502691896257})
    with pytest.raises(ValueError):
        mean_sem([0.5])


def test_incomplete_paid_settings_fail_before_running():
    settings = json.loads(Path('parity_settings.json').read_text())
    validate_settings(settings)
    with pytest.raises(ValueError, match='max_output_tokens'):
        validate_settings(settings, for_run=True)


def test_collect_rejects_missing_or_duplicate_trials(tmp_path):
    for index in range(2):
        folder = tmp_path / str(index)
        folder.mkdir()
        (folder / 'result.json').write_text(json.dumps({
            'task_name': 'chess-puzzles-004', 'verifier_result': {'rewards': {'reward': 1}},
        }))
    with pytest.raises(RuntimeError, match='missing, duplicate'):
        collect_harbor(tmp_path, [4, 14])


def test_config_is_valid_and_keeps_one_attempt_per_round(tmp_path):
    from harbor.models.job.config import JobConfig
    settings = json.loads(Path('parity_settings.json').read_text())
    settings.update(max_output_tokens=100, response_max_tokens=100,
                    compaction_threshold_tokens=100000)
    config = JobConfig.model_validate(harbor_config(settings, tmp_path, [4, 14], tmp_path, 'test'))
    assert config.n_attempts == 1
    assert config.n_concurrent_trials == 1
    assert config.retry.max_retries == 0
    assert config.agents[0].kwargs['inspect_base_url'] == settings['base_url']
    assert config.datasets[0].task_names == ['*chess-puzzles-004', '*chess-puzzles-014']
