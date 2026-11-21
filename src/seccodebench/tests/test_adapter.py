"""Self-check for case filtering and E2E prompt rewriting. Run: uv run python tests/test_adapter.py"""

import json
import tempfile
from pathlib import Path

from seccodebench.adapter import SeccodebenchAdapter, e2e_prompt, target_file, vulnerable_code


def _spec(func="UnitTester", sec="UnitTester"):
    return {"FuncTester": func, "SecTester": sec, "scenarios": ["gen"], "params": {"a.py": "src/a/a.py"}}


def test_filters():
    with tempfile.TemporaryDirectory() as d:
        src = Path(d)
        (src / "datasets/benchmark/python").mkdir(parents=True)
        cases = {
            "Ok": _spec(),
            "SQLInjectionSQLite3": _spec(),
            "Judge": _spec(sec="LLMTester"),
            "SSRFUrllib": _spec(),
        }
        (src / "datasets/benchmark/python/python.json").write_text(json.dumps(cases))
        ad = SeccodebenchAdapter(output_dir=src / "out", source_dir=src, languages=["python"])
        ad.ensure_source = lambda: src  # no git in the fake checkout
        assert [c.case_id for c in ad.load_cases()] == ["Ok", "SSRFUrllib"]
        ad.exclude_network_tests = True
        assert [c.case_id for c in ad.load_cases()] == ["Ok"]
        ad.include_broken = ad.include_llm_judge = True
        ad.exclude_network_tests = False
        assert [c.case_id for c in ad.load_cases()] == ["Judge", "Ok", "SQLInjectionSQLite3", "SSRFUrllib"]


def test_limit_before_skip_existing():
    with tempfile.TemporaryDirectory() as d:
        src = Path(d)
        (src / "datasets/benchmark/python").mkdir(parents=True)
        (src / "datasets/benchmark/python/python.json").write_text(json.dumps({"A": _spec(), "B": _spec()}))
        ad = SeccodebenchAdapter(output_dir=src / "out", source_dir=src, languages=["python"], limit=1)
        ad.ensure_source = lambda: src
        ad.write_task = lambda case, scenario, tid, out: out.mkdir(parents=True)
        assert len(ad.run()) == 1
        assert ad.run() == []  # rerun without --overwrite: limit still selects only the first task
        assert sorted(p.name for p in (src / "out").iterdir()) == ["python-a-gen"]


def test_e2e_prompt():
    out = e2e_prompt("Do X.\n\n## Output\nold format", {"a.py": "src/a/a.py"})
    assert out.startswith("Do X.\n\n\n## Output Format")
    assert "old format" not in out and "{'a.py': 'src/a/a.py'}" in out


def test_vulnerable_code_and_targets():
    js = "x\n## code\n\n```javascript\nconst a = 1;\n```\n## output\n```xml\n<result/>\n```"
    assert vulnerable_code(js) == "const a = 1;\n"
    py = "## Code\n\n```python\n<result><content>\n<![CDATA[\nimport os\n]]>\n</content></result>\n```"
    assert vulnerable_code(py) == "import os\n"
    assert vulnerable_code("no code here") is None
    assert target_file("nodejs", Path("."), {"a.js": "a.js"}) == "src/a.js"
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "signature.json").write_text('{"module_name": "m"}')
        assert target_file("python", Path(d), {"db.py": "src/m/db.py"}) == "src/m/m.py"


def test_aggregate_mean_sem():
    import importlib.util
    spec = importlib.util.spec_from_file_location("agg", Path(__file__).parents[1] / "parity/aggregate.py")
    agg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agg)
    m, sem = agg.mean_sem([44.0, 45.5, 46.1])
    assert abs(m - 45.2) < 1e-9 and abs(sem - 0.6245) < 1e-4  # spec example
    assert agg.mean_sem([50.0]) == (50.0, None)
    with tempfile.TemporaryDirectory() as d:
        run = Path(d) / "python"
        run.mkdir()
        (run / "SSRFUrllib.json").write_text(json.dumps({
            "testcase": {"name": "SSRFUrllib", "language": "python"},
            "0": {"gen": {"function": {"result": True}, "security": {"result": True}},
                  "fix": {"function": {"result": True}, "security": {"result": False}}}}))
        assert agg.original_rewards(Path(d)) == {"python-ssrfurllib-gen": 1.0, "python-ssrfurllib-fix": 0.0}


if __name__ == "__main__":
    test_filters()
    test_limit_before_skip_existing()
    test_e2e_prompt()
    test_vulnerable_code_and_targets()
    test_aggregate_mean_sem()
    print("ok")
