import json
from pathlib import Path

import pytest

from agentclinic.cases import (
    PARITY_SIZE,
    TOTAL_CASES,
    Case,
    load_cases,
    parity_indices,
    select,
)

FIXTURE = Path(__file__).parent / "fixtures" / "medqa_ext_sample.jsonl"


def _rows():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines()]


def _many(n):
    base = load_cases(FIXTURE)[0]
    return [
        Case(
            index=i,
            task_id=f"medqa-ext-{i:03d}",
            objective=base.objective,
            patient_actor=base.patient_actor,
            physical_exam=base.physical_exam,
            test_results=base.test_results,
            correct_diagnosis=base.correct_diagnosis,
        )
        for i in range(n)
    ]


def test_load_sample():
    cases = load_cases(FIXTURE)
    assert len(cases) == 3
    assert [c.task_id for c in cases] == ["medqa-ext-000", "medqa-ext-001", "medqa-ext-002"]
    assert cases[0].correct_diagnosis == "Myasthenia gravis"
    assert all(c.correct_diagnosis for c in cases)


def test_upstream_information_views():
    row = _rows()[0]["OSCE_Examination"]
    case = load_cases(FIXTURE)[0]
    assert case.examiner_information() == row["Objective_for_Doctor"]
    assert case.patient_information() == row["Patient_Actor"]
    exams = json.loads(json.dumps(row["Physical_Examination_Findings"]))
    exams["tests"] = row["Test_Results"]
    assert "{}".format(case.exam_information()) == "{}".format(exams)
    assert case.diagnosis_information() == row["Correct_Diagnosis"]


def test_exam_information_does_not_mutate_case():
    case = load_cases(FIXTURE)[0]
    case.exam_information()
    assert "tests" not in case.physical_exam


@pytest.mark.network
def test_load_full_count(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCLINIC_CACHE_DIR", str(tmp_path))
    cases = load_cases()
    assert len(cases) == TOTAL_CASES == 215
    assert cases[0].correct_diagnosis == "Myasthenia gravis"


def test_parity_split_is_pinned():
    assert parity_indices() == [
        6,
        7,
        8,
        22,
        23,
        26,
        28,
        35,
        55,
        57,
        59,
        62,
        70,
        108,
        129,
        139,
        151,
        163,
        173,
        188,
        189,
        211,
    ]


def test_loader_splits_on_newline_only(tmp_path):
    row = json.loads(FIXTURE.read_text().split("\n")[0])
    row["OSCE_Examination"]["Objective_for_Doctor"] += "\u2028extra"
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n")
    cases = load_cases(path)
    assert len(cases) == 1 and cases[0].objective.endswith("\u2028extra")


def test_parity_split_stable():
    first = parity_indices()
    assert first == parity_indices()
    assert len(first) == len(set(first)) == PARITY_SIZE == 22
    assert first == sorted(first)
    assert all(0 <= i < 215 for i in first)


def test_select_parity():
    cases = _many(215)
    chosen = select(cases, split="parity")
    assert [c.index for c in chosen] == parity_indices()


def test_task_ids_filter():
    cases = load_cases(FIXTURE)
    chosen = select(cases, task_ids=["medqa-ext-002", "medqa-ext-000"])
    assert [c.task_id for c in chosen] == ["medqa-ext-000", "medqa-ext-002"]


def test_unknown_task_id_raises():
    with pytest.raises(ValueError, match="medqa-ext-999"):
        select(load_cases(FIXTURE), task_ids=["medqa-ext-999"])


def test_limit():
    chosen = select(load_cases(FIXTURE), limit=2)
    assert [c.task_id for c in chosen] == ["medqa-ext-000", "medqa-ext-001"]


def test_unknown_split_raises():
    with pytest.raises(ValueError):
        select(load_cases(FIXTURE), split="nejm")


def test_stale_cache_is_replaced_atomically(tmp_path, monkeypatch):
    import io

    from agentclinic import cases as cases_module

    monkeypatch.setenv("AGENTCLINIC_CACHE_DIR", str(tmp_path))
    payload = b"payload"
    monkeypatch.setattr(cases_module, "DATA_SHA256", __import__("hashlib").sha256(payload).hexdigest())
    target = cases_module._cache_dir() / cases_module.DATA_FILE
    target.parent.mkdir(parents=True)
    target.write_bytes(b"truncated")

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    replaced = []
    real_replace = cases_module.os.replace
    monkeypatch.setattr(cases_module.urllib.request, "urlopen", lambda url, timeout: Response(payload))
    monkeypatch.setattr(
        cases_module.os, "replace", lambda src, dst: (replaced.append((src, dst)), real_replace(src, dst))
    )
    assert cases_module._download() == target
    assert target.read_bytes() == payload
    assert replaced and Path(replaced[0][1]) == target
    assert sorted(p.name for p in target.parent.iterdir()) == [cases_module.DATA_FILE]
