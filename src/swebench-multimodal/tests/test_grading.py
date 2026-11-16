import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from swebench_multimodal.adapter import SWEBenchMultimodalAdapter  # noqa: E402

TEMPLATE = ROOT / "src/swebench_multimodal/task-template/tests"
sys.path.insert(0, str(TEMPLATE))
from grade import grade  # noqa: E402


@pytest.mark.parametrize("task_number", ["10176", "10295"])
@pytest.mark.parametrize("status,reward", [("FAIL", "0"), ("PASS", "1")])
def test_lighthouse_reward_after_successful_cleanup(tmp_path, task_number, status, reward):
    source = tmp_path / "source"
    source.mkdir()
    fixture = Path(__file__).parent / "fixtures" / f"lighthouse-{task_number}"
    task_source = source / fixture.name
    shutil.copytree(fixture, task_source)
    (task_source / "gold.patch").write_text("synthetic unused oracle patch")
    (task_source / "problem_statement.md").write_text("Synthetic grading control")
    (task_source / "problem_assets").mkdir(exist_ok=True)
    metadata = yaml.safe_load((task_source / "task.yaml").read_text())
    gold = json.loads((task_source / "tests.json").read_text())
    case = gold["FAIL_TO_PASS"][0]
    (task_source / "eval.sh").write_text(
        "#!/bin/bash\nset -x\n"
        ": '>>>>> Start Test Output'\n"
        f"echo '{status} {case}'\n"
        + ("false\n" if status == "FAIL" else "true\n")
        + ": '>>>>> End Test Output'\n"
        "true # successful cleanup masks the test exit status\n"
    )
    task = SWEBenchMultimodalAdapter(
        tmp_path / "tasks", source_dir=source
    ).generate_task(metadata["instance_id"])
    tests_dir = task / "tests"
    assert json.loads((tests_dir / "task_metadata.json").read_text()) == metadata
    assert (tests_dir / "tests.json").read_bytes() == (fixture / "tests.json").read_bytes()
    assert subprocess.run(["bash", str(tests_dir / "eval.sh")], capture_output=True).returncode == 0

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "reward.txt").write_text("1")
    (log_dir / "reward.json").write_text('{"reward": 1}')
    script = (tests_dir / "test.sh").read_text()
    script = script.replace("/logs/verifier", str(log_dir))
    script = script.replace("/tests", str(tests_dir)).replace("/testbed", str(tmp_path))
    verifier = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert verifier.returncode == 0, verifier.stderr
    assert (log_dir / "reward.txt").read_text().strip() == reward
    assert not (log_dir / "reward.json").exists()
    report = json.loads((log_dir / "report.json").read_text())
    assert report["resolved"] is (reward == "1")
    assert report["valid_test_output"]
    assert case in report["tests_status"]["FAIL_TO_PASS"][
        "success" if reward == "1" else "failure"
    ]


@pytest.mark.parametrize(
    "eval_type,parser,output,f2p,p2p,resolved",
    [
        ("pass_and_fail", "parse_log_lighthouse", "PASS fix.js\nFAIL keep.js", ["fix.js"], ["keep.js"], False),
        ("pass_and_fail", "parse_log_lighthouse", "PASS other.js", ["fix.js"], [], False),
        ("pass_and_fail", "parse_log_lighthouse", "", ["fix.js"], [], False),
        ("pass_and_fail", "parse_log_lighthouse", "PASS fix.js", ["fix.js"], [], True),
        ("pass_and_fail", "parse_log_lighthouse", "PASS fix.js\nFAIL unrelated.js", ["fix.js"], [], True),
        ("fail_only", "parse_log_chart_js", "TOTAL: 1 SUCCESS", ["fix"], ["keep"], True),
        ("fail_only", "parse_log_chart_js", "TOTAL: 0 SUCCESS", ["fix"], [], False),
        ("fail_only", "parse_log_marked", "1) fix\n1 passing", ["fix"], [], False),
        ("fail_only", "parse_log_marked", "1) keep\n1 passing", ["fix"], ["keep"], False),
    ],
)
def test_upstream_grading_semantics(tmp_path, eval_type, parser, output, f2p, p2p, resolved):
    (tmp_path / "task_metadata.json").write_text(json.dumps({
        "instance_id": "grading-test",
        "version": "5.6",
        "log_parser": parser,
        "eval_type": eval_type,
    }))
    (tmp_path / "tests.json").write_text(json.dumps({
        "FAIL_TO_PASS": f2p, "PASS_TO_PASS": p2p,
    }))
    log = tmp_path / "test_output.log"
    log.write_text(f">>>>> Start Test Output\n{output}\n>>>>> End Test Output\n")
    assert grade(tmp_path, log)["resolved"] is resolved


@pytest.mark.parametrize("output", [
    "PASS fix.js",
    ">>>>> Start Test Output\nPASS fix.js",
    ">>>>> Patch Apply Failed\n>>>>> Start Test Output\nPASS fix.js\n>>>>> End Test Output",
])
def test_invalid_execution_is_unresolved(tmp_path, output):
    (tmp_path / "task_metadata.json").write_text(json.dumps({
        "instance_id": "grading-test", "version": "5.6",
        "log_parser": "parse_log_lighthouse", "eval_type": "pass_and_fail",
    }))
    (tmp_path / "tests.json").write_text('{"FAIL_TO_PASS":["fix.js"],"PASS_TO_PASS":[]}')
    log = tmp_path / "test_output.log"
    log.write_text(output)
    assert not grade(tmp_path, log)["resolved"]


@pytest.mark.parametrize("task_number,version", [("12970", "8.3"), ("13185", "8.6"), ("15054", "10.2")])
@pytest.mark.parametrize("output,resolved", [
    ("PASS ordinary-fix.js\nPASS ordinary-keep.js", True),
    ("FAIL ordinary-fix.js\nPASS ordinary-keep.js", False),
    ("PASS ordinary-fix.js", False),
])
def test_held_task_schema_with_synthetic_ordinary_tests(tmp_path, task_number, version, output, resolved):
    """Schema/interface substitute only, NOT execution or validation of held tasks.

    Metadata fields read from pinned public task.yaml; no source patch, evaluator,
    fixture, browser or container from these tasks is loaded or executed.
    """
    metadata = {
        "instance_id": f"GoogleChrome__lighthouse-{task_number}",
        "version": version,
        "log_parser": "parse_log_lighthouse",
        "eval_type": "pass_and_fail",
    }
    (tmp_path / "task_metadata.json").write_text(json.dumps(metadata))
    (tmp_path / "tests.json").write_text(json.dumps({
        "FAIL_TO_PASS": ["ordinary-fix.js"],
        "PASS_TO_PASS": ["ordinary-keep.js"],
    }))
    if version == "10.2":
        # Upstream 10.2 uses the Mocha reporter, not the older Jest format.
        output = "running 1 test files\n" + output.replace("PASS ", "  ✔ ").replace("FAIL ", "  1) ") + "\n1 passing"
    log = tmp_path / "synthetic.log"
    log.write_text(f">>>>> Start Test Output\n{output}\n>>>>> End Test Output\n")
    result = grade(tmp_path, log)
    assert result["instance_id"] == metadata["instance_id"]
    assert result["valid_test_output"]
    assert result["resolved"] is resolved


# Expected results independently checked against official commit 02e7a74,
# not inferred from the local wrapper. These are inert synthetic log strings.
_A = '>>>>> Start Test Output'
_B = '>>>>> End Test Output'
_P = 'PASS fix.js\nPASS keep.js'

def _framed(text):
    return _A + '\n' + text + '\n' + _B + '\n'


@pytest.mark.parametrize('log_text,alternate,valid,resolved', [
    (_framed(_P), False, True, True),
    (_framed('PASS fix.js'), False, True, False),
    (_framed('PASS fix.js\nFAIL keep.js'), False, True, False),
    (_P + '\n' + _B, False, False, False),
    (_A + '\n' + _P, False, False, False),
    ('>>>>> Patch Apply Failed\n' + _framed(_P), False, False, False),
    ('>>>>> Tests Errored\n' + _framed(''), False, False, False),
    ('>>>>> Tests Timed Out\n' + _framed(''), False, False, False),
    (_framed(''), False, False, False),
    (_framed('Tests: 0'), False, False, False),
    (_framed('') + _P, False, True, True),
    (_framed('TOTAL: 1 SUCCESS'), True, True, True),
    (_framed('TOTAL: 0 SUCCESS'), True, False, False),
    (_framed('PASS fix.js\nFAIL keep.js') + '>>>>> Test Exit Code: 1\n', False, True, False),
])
def test_independent_official_synthetic_baseline(tmp_path, log_text, alternate, valid, resolved):
    (tmp_path / 'task_metadata.json').write_text(json.dumps({
        'instance_id': 'synthetic-ordinary-conformance', 'version': '8.1',
        'log_parser': 'parse_log_chart_js' if alternate else 'parse_log_lighthouse',
        'eval_type': 'fail_only' if alternate else 'pass_and_fail',
    }))
    (tmp_path / 'tests.json').write_text(json.dumps({
        'FAIL_TO_PASS': ['fix.js'], 'PASS_TO_PASS': ['keep.js'],
    }))
    log = tmp_path / 'synthetic.log'
    log.write_text(log_text)
    actual = grade(tmp_path, log)
    assert actual['valid_test_output'] is valid
    assert actual['resolved'] is resolved
