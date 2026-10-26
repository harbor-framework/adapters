"""Offline contract checks. No Docker or model API is used."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from gdpval.adapter import TASK_TEMPLATE_DIR, GdpvalAdapter


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.row = {
            "task_id": "83d10b06-26d1-4636-a32c-23f92c57f30b",
            "prompt": "Produce the requested deliverables.\nKeep this source text.",
            "reference_files": ["reference_files/source.csv"],
            "deliverable_files": [
                "deliverable_files/report.txt",
                "deliverable_files/table.csv",
            ],
            "rubric_json": '{"criterion": "complete"}',
        }
        self.files = {
            "reference_files/source.csv": b"a,b\n1,2\n",
            "deliverable_files/report.txt": b"gold report\n",
            "deliverable_files/table.csv": b"x,y\n3,4\n",
        }

    def generate(self, **kwargs):
        def download(_adapter, raw, file_type):
            return self.files[raw], raw

        with (
            patch("gdpval.adapter.load_gdpval_dataset", return_value=[self.row]),
            patch.object(GdpvalAdapter, "_download_with_fallback", download),
        ):
            GdpvalAdapter(self.root / "tasks", **kwargs).run()
        return self.root / "tasks" / self.row["task_id"]

    def test_generation_and_cli_selection_contract(self):
        self.generate(task_ids=["unselected"])
        self.assertEqual(list((self.root / "tasks").iterdir()), [])
        self.generate(limit=0)
        self.assertEqual(list((self.root / "tasks").iterdir()), [])
        task = self.generate(task_ids=[self.row["task_id"]], limit=1)
        config = tomllib.loads((task / "task.toml").read_text())
        self.assertEqual(config["version"], "1.0")
        self.assertEqual(config["artifacts"], ["/app"])
        self.assertEqual(config["verifier"]["environment_mode"], "separate")
        self.assertEqual(config["environment"]["network_mode"], "public")
        self.assertTrue((task / "tests/Dockerfile").is_file())
        self.assertEqual(
            config["task"]["name"], "openai/gdpval__" + self.row["task_id"]
        )
        self.assertEqual(
            (task / "tests/task_prompt.txt").read_text(), self.row["prompt"]
        )
        self.assertEqual(
            (task / "tests/rubric.txt").read_text(), self.row["rubric_json"]
        )
        self.assertIn(self.row["prompt"], (task / "instruction.md").read_text())
        for name in ("report.txt", "table.csv"):
            gold = self.files["deliverable_files/" + name]
            self.assertEqual((task / "tests/gold" / name).read_bytes(), gold)
            self.assertEqual((task / "solution/gold" / name).read_bytes(), gold)
        self.assertEqual(
            (task / "environment/reference_files/source.csv").read_bytes(),
            self.files["reference_files/source.csv"],
        )
        before = {
            str(p.relative_to(task)): p.read_bytes()
            for p in task.rglob("*")
            if p.is_file()
        }
        self.generate(overwrite=True)
        after = {
            str(p.relative_to(task)): p.read_bytes()
            for p in task.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        marker = task / "keep.txt"
        marker.write_text("keep")
        self.generate(overwrite=False)
        self.assertTrue(marker.exists())

    def test_missing_and_exact_gold_shell_paths_without_judge(self):
        task = self.generate()
        app, logs = self.root / "app", self.root / "logs"
        app.mkdir()
        # Map container paths into a disposable directory. This is a host replay,
        # not proof of Docker mounts, permissions, networking, or agent isolation.
        script = (task / "tests/test.sh").read_text()
        for source, target in (
            ("/logs/verifier", logs),
            ("/tests", task / "tests"),
            ("/app", app),
        ):
            script = script.replace(source, str(target))
        subprocess.run(["bash", "-c", script], check=True, capture_output=True)
        self.assertEqual(float((logs / "reward.txt").read_text()), 0)
        for gold in (task / "solution/gold").iterdir():
            (app / gold.name).write_bytes(gold.read_bytes())
        subprocess.run(["bash", "-c", script], check=True, capture_output=True)
        self.assertEqual(float((logs / "reward.txt").read_text()), 1)
        result = json.loads((logs / "rubric_judge.json").read_text())
        self.assertTrue(result["deterministic_exact_match"])

    def test_offline_profile_is_explicit_and_keeps_inputs(self):
        task = self.generate(agent_network="no-network")
        config = tomllib.loads((task / "task.toml").read_text())
        self.assertEqual(config["environment"]["network_mode"], "no-network")
        self.assertEqual(config["verifier"]["environment"]["network_mode"], "public")
        compose = (task / "environment/docker-compose.yaml").read_text()
        self.assertIn("network_mode: none", compose)
        self.assertNotIn("cap_add", compose)
        self.assertIn(self.row["prompt"], (task / "instruction.md").read_text())
        with self.assertRaises(ValueError):
            GdpvalAdapter(self.root, agent_network="invalid")

    def test_pairwise_judge_offline(self):
        spec = importlib.util.spec_from_file_location(
            "gdpval_judge", TASK_TEMPLATE_DIR / "tests/rubric_judge.py"
        )
        judge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(judge)
        model, gold = self.root / "model", self.root / "gold"
        model.mkdir()
        gold.mkdir()
        (model / "report.txt").write_text("candidate")
        (gold / "report.txt").write_text("reference")
        for winner, reward in (("model", 1.0), ("tie", 0.5), ("gold", 0.0)):
            response = {
                "choices": [
                    {
                        "message": {
                            "content": "```json\n"
                            + json.dumps({"winner": winner})
                            + "\n```"
                        }
                    }
                ]
            }
            with patch.object(
                judge.litellm, "completion", return_value=response
            ) as completion:
                result = judge.judge(
                    task_id="offline",
                    task_prompt="prompt",
                    rubric="rubric",
                    model_deliverable=model,
                    gold_deliverable=gold,
                    expected_deliverables=["report.txt"],
                    judge_model="openai/gpt-5",
                )
            self.assertEqual(result["score"], reward)
            self.assertEqual(
                [m["role"] for m in completion.call_args.kwargs["messages"]],
                ["system", "user"],
            )

        for malformed in ({}, {"winner": "unknown"}, {"score": 0.2}, {"score": True}, []):
            with self.subTest(malformed=malformed), self.assertRaises((TypeError, ValueError)):
                judge._normalize_judge_result(malformed)

    def test_verifier_infrastructure_error_is_unscored(self):
        task = self.generate()
        app, logs = self.root / "app", self.root / "logs"
        app.mkdir()
        logs.mkdir()
        (logs / "reward.json").write_text('{"reward": 1}')
        (logs / "reward.txt").write_text("1")
        # Missing gold is an infrastructure error, even with missing outputs.
        (task / "tests/gold/report.txt").unlink()
        script = (task / "tests/test.sh").read_text()
        for source, target in (
            ("/logs/verifier", logs), ("/tests", task / "tests"), ("/app", app),
        ):
            script = script.replace(source, str(target))
        result = subprocess.run(["bash", "-c", script], capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((logs / "reward.txt").exists())
        self.assertFalse((logs / "reward.json").exists())
        self.assertEqual(json.loads((logs / "error.json").read_text())["status"], "verifier_error")


if __name__ == "__main__":
    unittest.main()
