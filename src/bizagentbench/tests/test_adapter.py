import hashlib
import json
from pathlib import Path
import tomllib

import pytest
from bizagentbench.adapter import BizAgentBenchAdapter
from bizagentbench.source import UPSTREAM_COMMIT
from conftest import SOURCE


def test_selection_names_isolation_and_reproducibility(tmp_path):
    adapter = BizAgentBenchAdapter(tmp_path, SOURCE, task_ids=["case_031", "case_001"])
    paths = adapter.run()
    assert [path.name for path in paths] == ["bizagentbench-case-001", "bizagentbench-case-031"]
    before = {}
    for path in paths:
        config = tomllib.loads((path / "task.toml").read_text("utf-8"))
        assert config["version"] == "1.0"
        assert config["verifier"]["environment_mode"] == "separate"
        assert config["verifier"]["collect"][0]["service"] == "business"
        assert config["artifacts"][0]["service"] == "business"
        assert config["task"]["name"] == "ant-intl/" + path.name
        source = json.loads((path / "source.json").read_text("utf-8"))
        assert source["commit"] == UPSTREAM_COMMIT
        assert source["archive_sha256"] == hashlib.sha256((path / "tests/upstream.tar").read_bytes()).hexdigest()
        docker = (path / "environment/Dockerfile").read_text("utf-8")
        assert "COPY ." not in docker
        assert "COPY biz.py" in docker
        assert not (path / "environment/solution").exists()
        assert not (path / "solution/trajectory.json").exists()
        before[path.name] = (path / "source.json").read_bytes()
    with pytest.raises(FileExistsError):
        adapter.run()
    adapter.overwrite = True
    for path in adapter.run():
        assert before[path.name] == (path / "source.json").read_bytes()


def test_invalid_ids_and_limits_fail_before_generation(tmp_path):
    with pytest.raises(ValueError, match="Unknown"):
        BizAgentBenchAdapter(tmp_path, SOURCE, task_ids=["../case_001"]).run()
    with pytest.raises(ValueError, match="positive"):
        BizAgentBenchAdapter(tmp_path, SOURCE, limit=0).run()
    assert not list(tmp_path.iterdir())


def test_overwrite_rejects_unrelated_directory(tmp_path):
    target = tmp_path / "bizagentbench-case-001"
    target.mkdir()
    with pytest.raises(ValueError, match="unrelated"):
        BizAgentBenchAdapter(tmp_path, SOURCE, limit=1, overwrite=True).run()
    assert target.is_dir()
