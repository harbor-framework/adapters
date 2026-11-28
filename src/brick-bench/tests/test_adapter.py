"""Unit tests for the BrickBench Harbor adapter and verifier logic."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

from brick_bench.adapter import (
    CATEGORIES,
    ORACLE_SMOKE_TASK_IDS,
    PARITY_TASK_IDS,
    BrickBenchAdapter,
    render_instruction,
    sanitize_task_name,
    task_category,
)
from brick_bench.main import main

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "src" / "brick_bench" / "task-template"
GRADE_PY = TEMPLATE_DIR / "tests" / "grade.py"


def _load_grade_module():
    spec = importlib.util.spec_from_file_location("brickbench_grade_test", GRADE_PY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_fake_upstream(root: Path, *, per_split: int = 100) -> tuple[Path, Path]:
    """Create a minimal synthetic upstream BrickAgent checkout and oracle dir."""
    repo = root / "BrickAgent"
    oracle = root / "oracle"

    prompt_tpl = (
        "Your task is to design a high-quality LEGO set depicting:\n"
        "{{ object_prompt }}\n"
        "{% if split == 'model' %}\n- Use **at most 400 pieces**.\n"
        "{% elif split == 'set' %}\n- Use **400–4000 pieces, inclusive**.\n"
        "{% elif split == 'alt-build' %}\n- Use only the supplied parts and colors.\n"
        "{% endif %}\n"
        "Deliver `build.py` and `model.mpd`.\n"
    )
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "prompt.md").write_text(prompt_tpl, encoding="utf-8")

    inv = {"3001": {"red": 8, "blue": 6}}
    (repo / "benchmark" / "alt-build").mkdir(parents=True)
    (repo / "benchmark" / "alt-build" / "inventory.json").write_text(
        json.dumps(inv, indent=2) + "\n", encoding="utf-8"
    )

    split_prefixes = {"model": "model", "set": "set", "alt-build": "alt"}
    hf_splits = {"model": "model", "set": "set", "alt-build": "alt"}
    for split, prefix in split_prefixes.items():
        sdir = repo / "benchmark" / split
        sdir.mkdir(parents=True, exist_ok=True)
        tasks = []
        for idx in range(1, per_split + 1):
            tid = f"{prefix}-{idx:03d}"
            tasks.append(
                {
                    "id": tid,
                    "prompt": f"Build prompt for {tid}.",
                    "questions": [
                        {
                            "key": "root",
                            "question": f"Is {tid} recognizable?",
                            "kind": "entity",
                            "subtype": "whole",
                            "dependencies": [],
                        },
                        {
                            "key": "detail",
                            "question": f"Does {tid} have the requested color?",
                            "kind": "attribute",
                            "subtype": "color",
                            "dependencies": ["root"],
                        },
                    ],
                }
            )
            odir = oracle / "astra" / hf_splits[split] / tid
            odir.mkdir(parents=True, exist_ok=True)
            (odir / "build.py").write_text(
                f'"""Oracle for {tid}."""\ndef build():\n    return None\n',
                encoding="utf-8",
            )
        (sdir / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")

    return repo, oracle


def test_task_category_and_name_sanitization():
    assert task_category("model-001") == CATEGORIES[0]
    assert task_category("model-010") == CATEGORIES[0]
    assert task_category("model-011") == CATEGORIES[1]
    assert task_category("alt-100") == CATEGORIES[9]
    assert sanitize_task_name("model-001") == "brickbench/model-001"
    assert sanitize_task_name("Alt_001/Test") == "brickbench/alt-001-test"
    with pytest.raises(ValueError):
        task_category("model-101")


def test_generate_all_300_tasks_and_layout(tmp_path: Path):
    repo, oracle = _make_fake_upstream(tmp_path, per_split=100)
    out = tmp_path / "datasets" / "brick-bench"

    adapter = BrickBenchAdapter(
        output_dir=out,
        split="all",
        repo_path=repo,
        oracle_dir=oracle,
        overwrite=True,
    )
    generated = adapter.run()
    assert len(generated) == 300

    names: set[str] = set()
    for task_dir in generated:
        toml_data = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        assert toml_data["version"] == "1.0"
        assert toml_data["artifacts"] == ["/work"]
        assert toml_data["verifier"]["environment_mode"] == "separate"
        assert toml_data["verifier"]["environment"]["gpus"] == 1
        assert len(toml_data["task"]["authors"]) == 5
        names.add(toml_data["task"]["name"])

        split = toml_data["metadata"]["split"]
        instr = (task_dir / "instruction.md").read_text(encoding="utf-8")
        assert f"Build prompt for {task_dir.name}." in instr

        env_df = (task_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
        if split == "alt-build":
            assert "BRICKAGENT_SET=/opt/brickbench/inventory.json" in env_df
            assert (task_dir / "environment" / "inventory.json").is_file()
            assert (task_dir / "tests" / "inventory.json").is_file()
            assert "Use only the supplied parts and colors." in instr
        else:
            assert "BRICKAGENT_SET" not in env_df
            assert not (task_dir / "environment" / "inventory.json").exists()
            assert not (task_dir / "tests" / "inventory.json").exists()

        assert (task_dir / "solution" / "solve.sh").is_file()
        assert (task_dir / "solution" / "build.py").is_file()
        assert (task_dir / "tests" / "Dockerfile").is_file()
        assert (task_dir / "tests" / "test.sh").is_file()
        assert (task_dir / "tests" / "grade.py").is_file()
        task_json = json.loads((task_dir / "tests" / "task.json").read_text(encoding="utf-8"))
        assert task_json["id"] == task_dir.name
        assert task_json["split"] == split
        assert len(task_json["questions"]) == 2

    assert len(names) == 300


def test_cli_splits_task_ids_limit_and_overwrite(tmp_path: Path):
    repo, oracle = _make_fake_upstream(tmp_path, per_split=100)

    out_parity = tmp_path / "parity"
    main(["--output-dir", str(out_parity), "--split", "parity", "--repo-path", str(repo), "--oracle-dir", str(oracle)])
    assert sorted(p.name for p in out_parity.iterdir()) == sorted(PARITY_TASK_IDS)
    assert len(PARITY_TASK_IDS) == 30

    out_smoke = tmp_path / "smoke"
    main(
        [
            "--output-dir",
            str(out_smoke),
            "--split",
            "oracle-smoke",
            "--repo-path",
            str(repo),
            "--oracle-dir",
            str(oracle),
        ]
    )
    assert sorted(p.name for p in out_smoke.iterdir()) == sorted(ORACLE_SMOKE_TASK_IDS)
    assert len(ORACLE_SMOKE_TASK_IDS) == 9

    out_filtered = tmp_path / "filtered"
    main(
        [
            "--output-dir",
            str(out_filtered),
            "--task-ids",
            "model-001",
            "set-011",
            "alt-021",
            "--limit",
            "2",
            "--repo-path",
            str(repo),
            "--oracle-dir",
            str(oracle),
        ]
    )
    assert sorted(p.name for p in out_filtered.iterdir()) == ["model-001", "set-011"]

    # Without --overwrite, existing directory is preserved.
    marker = out_filtered / "model-001" / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    main(
        [
            "--output-dir",
            str(out_filtered),
            "--task-ids",
            "model-001",
            "--repo-path",
            str(repo),
            "--oracle-dir",
            str(oracle),
        ]
    )
    assert marker.exists()

    # With --overwrite, existing directory is regenerated cleanly.
    main(
        [
            "--output-dir",
            str(out_filtered),
            "--task-ids",
            "model-001",
            "--overwrite",
            "--repo-path",
            str(repo),
            "--oracle-dir",
            str(oracle),
        ]
    )
    assert not marker.exists()


def test_render_instruction_strict_undefined():
    tpl = "Prompt: {{ object_prompt }} Split: {{ split }}\n"
    assert render_instruction(tpl, "A lighthouse", "model") == "Prompt: A lighthouse Split: model\n"


def test_grade_flatten_mpd_expands_submodels_and_color_16():
    grade = _load_grade_module()
    mpd = (
        "0 FILE main.ldr\n"
        "1 4 10 20 30 1 0 0 0 1 0 0 0 1 sub.ldr\n"
        "0 NOFILE\n"
        "0 FILE sub.ldr\n"
        "1 16 1 2 3 1 0 0 0 1 0 0 0 1 3001.dat\n"
        "1 14 0 0 0 1 0 0 0 1 0 0 0 1 3005.dat\n"
        "0 NOFILE"
    )
    flattened = grade.flatten_mpd(mpd, "test_model")
    lines = flattened.splitlines()
    assert lines[0] == "0 test_model"
    assert lines[1] == "0 Name: test_model.ldr"
    assert lines[2] == "1 4 11 22 33 1 0 0 0 1 0 0 0 1 3001.dat"
    assert lines[3] == "1 14 10 20 30 1 0 0 0 1 0 0 0 1 3005.dat"
    assert np.isfinite(1.0)


def test_grade_vqa_prompt_parse_and_dependency_gating():
    grade = _load_grade_module()
    task = {
        "id": "model-001",
        "split": "model",
        "prompt": "A red brick castle.",
        "questions": [
            {"key": "castle", "question": "Is there a castle?", "dependencies": []},
            {"key": "castle.color", "question": "Is the castle red?", "dependencies": ["castle"]},
            {"key": "flag", "question": "Is there a flag?", "dependencies": []},
        ],
    }

    sheet = grade.format_vqa_prompt(task)
    assert "A red brick castle." in sheet
    assert "1. Is there a castle?" in sheet
    assert "3. Is there a flag?" in sheet
    assert "End your reply with exactly 3 lines" in sheet

    # Dependency gating: castle=no blocks castle.color=yes.
    reply = "Reasoning...\n1: no\n2: yes\n3: yes\n"
    verdicts = grade.parse_vqa_reply(task, reply)
    assert verdicts == {"castle": "no", "castle.color": "yes", "flag": "yes"}
    scores = grade.score_vqa(task, verdicts)
    assert scores["flat"] == pytest.approx(2 / 3)
    assert scores["gated"] == pytest.approx(1 / 3)

    # Missing question -> None (judge parse failure, not a silent 0).
    assert grade.parse_vqa_reply(task, "1: yes\n2: yes\n") is None


def test_grade_resolve_local_model_dir(tmp_path: Path):
    grade = _load_grade_module()
    rev = "842da3794eaa0b77d5f08bae87a17459d91ff475"
    snap = tmp_path / "hub" / "models--google--gemma-4-31B-it" / "snapshots" / rev
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")

    found = grade._resolve_local_model_dir("google/gemma-4-31B-it", rev, tmp_path)
    assert found == snap
    assert grade._resolve_local_model_dir("google/gemma-4-31B-it", "other", tmp_path) is None
