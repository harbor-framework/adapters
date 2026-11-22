"""Offline preparation cannot silently become a model execution authorization."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preparation_check', ROOT / 'scripts/check_preparation.py')
checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)


def inputs():
    return [json.loads((ROOT / 'preparation' / name).read_text('utf-8'))
            for name in ('experiment-plan.json', 'model.draft.json', 'first-batch.json')]


def test_disabled_preparation_is_consistent():
    assert checker.validate_draft(*inputs())


@pytest.mark.parametrize('change', ['enabled', 'spend', 'credential', 'endpoint', 'duplicate', 'asymmetric'])
def test_preparation_rejects_unsafe_or_inconsistent_changes(change):
    plan, model, selection = deepcopy(inputs())
    if change == 'enabled': plan['execution']['enabled'] = True
    elif change == 'spend': plan['execution']['authorized_spend_usd'] = 1
    elif change == 'credential': model['user']['api_key'] = 'dummy-not-a-real-secret'
    elif change == 'endpoint': model['user']['base_url'] = 'https://provider.example/v1'
    elif change == 'duplicate': selection['tasks'][1]['task_id'] = selection['tasks'][0]['task_id']
    elif change == 'asymmetric': plan['phases'][-1]['run_order'][1] = 'native_r2'
    with pytest.raises(ValueError): checker.validate_draft(plan, model, selection)
