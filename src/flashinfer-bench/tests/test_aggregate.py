from pathlib import Path

import pytest

from flashinfer_bench.aggregate import aggregate


def test_scored_failures_count_but_missing_results_are_not_zero():
    assert aggregate([{"reward": 4.0}, {"reward": 0.0}, None, {}]) == {
        "avg_speedup": 2.0,
        "scored_definitions": 2,
        "unscored_definitions": 2,
    }
    assert aggregate([None]) == {"scored_definitions": 0, "unscored_definitions": 1}
    assert aggregate([]) == {"scored_definitions": 0, "unscored_definitions": 0}


@pytest.mark.parametrize(
    "reward,error",
    [
        ({"reward": float("nan")}, ValueError),
        ({"reward": "2"}, TypeError),
        ({"wrong": 2}, KeyError),
    ],
)
def test_invalid_rewards_are_not_silently_dropped(reward, error):
    with pytest.raises(error):
        aggregate([reward])


def test_reference_config_uses_metric_through_harbor():
    pytest.importorskip("harbor")
    import yaml
    from harbor.metrics.factory import MetricFactory
    from harbor.models.metric.config import MetricConfig

    root = Path(__file__).parents[1]
    config = yaml.safe_load((root / "run_flashinfer-bench.yaml").read_text())
    metric_config = MetricConfig.model_validate(config["metrics"][0])
    metric_config.kwargs["script_path"] = root / metric_config.kwargs["script_path"]
    metric = MetricFactory.create_metric(metric_config.type, **metric_config.kwargs)
    assert metric.compute([{"reward": 4.0}, {"reward": 0.0}, None]) == {
        "avg_speedup": 2.0,
        "scored_definitions": 2,
        "unscored_definitions": 1,
    }
