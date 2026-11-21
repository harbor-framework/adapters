"""Verifier layout and stale dataset guards; Docker controls are a separate smoke run."""
import json
import tomllib

import pytest
from harbor.models.task.config import TaskConfig
from harbor.models.task.paths import TaskPaths
from harbor.models.task.verifier_mode import resolve_verifier_environment_definition

from chess_puzzles.adapter import ChessPuzzlesAdapter
from chess_puzzles.parity import verify_dataset
from chess_puzzles.source import prepare_source


@pytest.mark.parametrize('variant', ['original', 'cli'])
def test_verifier_uses_tests_image_and_only_answer_artifact(tmp_path, variant):
    csv = prepare_source() / 'bench/task/chess_puzzles/puzzles.csv'
    tasks = ChessPuzzlesAdapter(tmp_path, data_path=csv, variant=variant, limit=1).run()
    task = tasks[0]
    config = TaskConfig.model_validate(tomllib.loads((task / 'task.toml').read_text()))
    definition = resolve_verifier_environment_definition(config, TaskPaths(task))
    assert definition is not None and definition.bundled_tests
    assert definition.directory == task / 'tests'
    assert definition.config.network_mode == 'public'
    assert config.artifacts == ['/app/answer.txt']
    assert 'COPY . /tests/' in (definition.directory / 'Dockerfile').read_text()
    assert not (task / 'environment/record.json').exists()
    assert '/tests' not in (task / 'environment/Dockerfile').read_text()


@pytest.mark.parametrize('damage', ['old-manifest', 'shared', 'artifact', 'image', 'old-network-policy', 'missing-dockerfile'])
def test_prepared_parity_rejects_old_or_misconfigured_verifier(tmp_path, damage):
    csv = prepare_source() / 'bench/task/chess_puzzles/puzzles.csv'
    tasks = ChessPuzzlesAdapter(tmp_path, data_path=csv, split='parity').run()
    verify_dataset(tmp_path)
    config_path = tasks[0] / 'task.toml'
    text = config_path.read_text()
    if damage == 'old-manifest':
        path = tmp_path / 'generation_manifest.json'
        manifest = json.loads(path.read_text())
        manifest.pop('verifier_mode')
        path.write_text(json.dumps(manifest))
    elif damage == 'shared':
        config_path.write_text(text.replace('environment_mode = "separate"', 'environment_mode = "shared"'))
    elif damage == 'artifact':
        config_path.write_text(text.replace('artifacts = ["/app/answer.txt"]', 'artifacts = ["/app"]'))
    elif damage == 'image':
        config_path.write_text(text.replace('[verifier.environment]', '[verifier.environment]\ndocker_image = "agent-image"'))
    elif damage == 'old-network-policy':
        config_path.write_text(text.replace('[verifier.environment]', '[verifier.environment]\nnetwork_mode = "no-network"'))
    else:
        (tasks[0] / 'tests/Dockerfile').unlink()
    with pytest.raises(ValueError, match='separate'):
        verify_dataset(tmp_path)
