"""Offline generation checks use synthetic encrypted records only."""

import base64
import hashlib
import json
import tomllib
from pathlib import Path

import pytest
import yaml

from browsecomp_plus import adapter as adapter_module
from browsecomp_plus.adapter import DEFAULT_CANARY, BrowseCompPlusAdapter


def _encrypt(text: str) -> str:
    plaintext = text.encode("utf-8")
    digest = hashlib.sha256(DEFAULT_CANARY.encode("utf-8")).digest()
    key = (digest * (len(plaintext) // len(digest) + 1))[: len(plaintext)]
    return base64.b64encode(bytes(a ^ b for a, b in zip(plaintext, key))).decode()


@pytest.fixture
def synthetic_dataset(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    def refuse_download(*args, **kwargs):
        raise AssertionError("Synthetic generation must never fetch a dataset")

    monkeypatch.setattr(adapter_module, "load_dataset", refuse_download)
    return [
        {
            "query_id": "Synthetic ID",
            "query": _encrypt("Synthetic fixture question 1842?"),
            "answer": _encrypt("SYNTHETIC_ANSWER_SENTINEL_7619"),
            "gold_docs": [_encrypt("synthetic-document-1")],
            "evidence_docs": [{"docid": _encrypt("synthetic-document-2")}],
            "negative_docs": [],
        }
    ]


def test_generation_keeps_answer_out_of_environment_assets(
    tmp_path: Path, synthetic_dataset: list[dict]
) -> None:
    adapter = BrowseCompPlusAdapter(tmp_path, dataset=synthetic_dataset)

    assert adapter.run() == (1, 0, 1)

    task_dir = tmp_path / "synthetic-id"
    instruction = (task_dir / "instruction.md").read_text()
    assert "Synthetic fixture question 1842?" in instruction
    assert "SYNTHETIC_ANSWER_SENTINEL_7619" not in instruction
    config = json.loads((task_dir / "tests/config.json").read_text())
    assert config["answer"] == "SYNTHETIC_ANSWER_SENTINEL_7619"
    assert config["query_id"] == "Synthetic ID"
    assert config["gold_docs"] == ["synthetic-document-1"]
    assert config["evidence_docs"] == [{"docid": "synthetic-document-2"}]
    assert json.loads((task_dir / "solution/oracle_config.json").read_text()) == {
        "answer": "SYNTHETIC_ANSWER_SENTINEL_7619"
    }
    for path in (task_dir / "environment").rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            assert b"SYNTHETIC_ANSWER_SENTINEL_7619" not in content
            assert b"Synthetic fixture question 1842?" not in content

    compose = yaml.safe_load((task_dir / "environment/docker-compose.yaml").read_text())
    volume_sources = [
        value.split(":", 1)[0] for value in compose["services"]["main"]["volumes"]
    ]
    assert "./tests" not in volume_sources
    assert "../tests" not in volume_sources
    assert "./solution" not in volume_sources
    assert "../solution" not in volume_sources
    task_config = tomllib.loads((task_dir / "task.toml").read_text())
    assert task_config["task"]["name"] == "texttron/browsecomp-plus-synthetic-id"
    assert "__TASK_NAME__" not in (task_dir / "task.toml").read_text()
    for script in [task_dir / "solution/solve.sh", task_dir / "tests/test.sh"]:
        assert script.stat().st_mode & 0o111


def test_existing_tasks_require_explicit_overwrite(
    tmp_path: Path, synthetic_dataset: list[dict]
) -> None:
    adapter = BrowseCompPlusAdapter(tmp_path, dataset=synthetic_dataset)
    assert adapter.run() == (1, 0, 1)
    instruction_path = tmp_path / "synthetic-id/instruction.md"
    instruction_path.write_text("Synthetic local edit")

    assert adapter.run() == (0, 1, 1)
    assert instruction_path.read_text() == "Synthetic local edit"
    assert adapter.run(overwrite=True) == (1, 0, 1)
    assert "Synthetic fixture question 1842?" in instruction_path.read_text()
