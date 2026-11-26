import csv
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from or_bench.adapter import (
    BASE_IMAGE,
    HARD_1K_ANSWERS_PATH,
    SAFE_ORACLE_TEMPLATE,
    TOXIC_ORACLE_RESPONSE,
    DEFAULT_JUDGE_MODEL,
    SUBSET_FILES,
    TEMPLATE_DIR,
    OrBenchAdapter,
    parity_sample,
)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.data.mkdir()
        for subset, name in SUBSET_FILES.items():
            with open(self.data / name, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["prompt", "category"])
                w.writerow([f"{subset} prompt with {{braces}}", "violence"])

    def generate(self, out, **kwargs):
        OrBenchAdapter(self.tmp / out, data_dir=self.data, **kwargs).run()
        return sorted((self.tmp / out).iterdir())

    def test_default_has_no_docker_image(self):
        for task in self.generate("default"):
            cfg = tomllib.loads((task / "task.toml").read_text())
            self.assertNotIn("docker_image", cfg["environment"])
            self.assertTrue((task / "environment" / "Dockerfile").exists())

    def test_prebuilt_image_sets_base_image(self):
        for task in self.generate("prebuilt", prebuilt_image=True):
            cfg = tomllib.loads((task / "task.toml").read_text())
            self.assertEqual(cfg["environment"]["docker_image"], BASE_IMAGE)
            self.assertTrue((task / "environment" / "Dockerfile").exists())

    def test_base_image_matches_dockerfile(self):
        dockerfile = (TEMPLATE_DIR / "environment" / "Dockerfile").read_text()
        self.assertIn(f"FROM {BASE_IMAGE}\n", dockerfile)

    def test_modes_differ_only_in_docker_image(self):
        default = {p.name: p for p in self.generate("default")}
        prebuilt = {p.name: p for p in self.generate("prebuilt", prebuilt_image=True)}
        self.assertEqual(default.keys(), prebuilt.keys())
        for name in default:
            a, b = default[name], prebuilt[name]
            files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
            self.assertEqual(files, sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file()))
            for rel in files:
                ta, tb = (a / rel).read_text(), (b / rel).read_text()
                if rel.name == "task.toml":
                    tb = tb.replace(f'docker_image = "{BASE_IMAGE}"\n', "", 1)
                self.assertEqual(ta, tb, f"{name}/{rel}")


    def judges(self, out, **kwargs):
        result = {}
        for task in self.generate(out, **kwargs):
            cfg = tomllib.loads((task / "task.toml").read_text())
            gt = json.loads((task / "tests" / "ground_truth.json").read_text())
            self.assertEqual(cfg["metadata"]["judge"], gt["judge"])
            # The verifier runs in a fresh container; the agent's outputs reach it as artifacts.
            self.assertEqual(cfg["verifier"]["environment_mode"], "separate")
            self.assertNotIn("environment", cfg["verifier"])
            self.assertEqual(cfg["artifacts"], ["/app/response.txt", "/logs/agent"])
            self.assertFalse((task / "tests" / "Dockerfile").exists())
            result[gt["subset"]] = (gt["judge"], cfg["verifier"])
        return result

    def test_auto_judge_follows_paper(self):
        j = self.judges("auto")
        self.assertEqual({k: v[0] for k, v in j.items()},
                         {"80k": "keyword", "hard-1k": "llm", "toxic": "llm"})
        self.assertEqual(j["80k"][1], {"environment_mode": "separate", "timeout_sec": 60.0})
        llm = j["toxic"][1]
        self.assertEqual(llm["network_mode"], "public")
        self.assertEqual(llm["env"], {
            "OPENAI_API_KEY": "${OPENAI_API_KEY}",
            "OPENAI_BASE_URL": "${OPENAI_BASE_URL:-}",
            "JUDGE_MODEL": f"${{JUDGE_MODEL:-{DEFAULT_JUDGE_MODEL}}}",
        })

    def test_judge_override(self):
        for judge in ("keyword", "llm"):
            with self.subTest(judge=judge):
                j = self.judges(judge, judge=judge)
                self.assertEqual({v[0] for v in j.values()}, {judge})

    def test_invalid_judge(self):
        with self.assertRaises(ValueError):
            OrBenchAdapter(self.tmp / "x", judge="gpt")

    def test_prompt_file_for_judge(self):
        for task in self.generate("default"):
            prompt = (task / "tests" / "prompt.txt").read_text()
            self.assertTrue(prompt.endswith("prompt with {braces}"))
            self.assertIn(prompt, (task / "instruction.md").read_text())

    def test_oracle_sources(self):
        answers = json.loads(HARD_1K_ANSWERS_PATH.read_text(encoding="utf-8"))
        for task in self.generate("oracle"):
            gt = json.loads((task / "tests" / "ground_truth.json").read_text())
            got = (task / "solution" / "response.txt").read_text()
            if gt["subset"] == "hard-1k":
                self.assertEqual(got, answers[gt["id"]])
            elif gt["subset"] == "toxic":
                self.assertEqual(got, TOXIC_ORACLE_RESPONSE)
            else:
                prompt = (task / "tests" / "prompt.txt").read_text()
                self.assertEqual(got, SAFE_ORACLE_TEMPLATE.replace("{prompt}", prompt))

    def test_stored_hard_1k_answers(self):
        self.assertEqual(HARD_1K_ANSWERS_PATH.parent.name, "oracle_solutions")
        answers = json.loads(HARD_1K_ANSWERS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(answers), [f"hard-1k-{i:05d}" for i in range(1319)])
        self.assertTrue(all(v.strip() for v in answers.values()))
        # only hard-1k is stored; 80k and toxic are rule-generated
        self.assertEqual([p.name for p in HARD_1K_ANSWERS_PATH.parent.iterdir()], ["hard-1k.json"])


class ParitySampleTests(unittest.TestCase):
    @staticmethod
    def records():
        # 3 subsets x 3 categories of unequal size (60 / 30 / 10 rows each)
        recs = []
        for subset in ("80k", "hard-1k", "toxic"):
            for cat, n in (("a", 60), ("b", 30), ("c", 10)):
                recs += [{"id": f"{subset}-{cat}{i}", "subset": subset, "category": cat} for i in range(n)]
        return recs

    def test_size_and_stratification(self):
        sample = parity_sample(self.records(), per_subset=20)
        for subset in ("80k", "hard-1k", "toxic"):
            cats = [r["category"] for r in sample if r["subset"] == subset]
            self.assertEqual(len(cats), 20)
            self.assertEqual({c: cats.count(c) for c in "abc"}, {"a": 12, "b": 6, "c": 2})

    def test_deterministic_and_seed_dependent(self):
        recs = self.records()
        self.assertEqual(parity_sample(recs, 20), parity_sample(recs, 20))
        self.assertNotEqual(parity_sample(recs, 20), parity_sample(recs, 20, seed=1))

    def test_small_subset_is_kept_whole(self):
        recs = [{"id": f"toxic-{i}", "subset": "toxic", "category": "a"} for i in range(5)]
        self.assertEqual(len(parity_sample(recs, 100)), 5)

    def test_split_parity_selects_only_the_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = OrBenchAdapter(Path(tmp), split="parity")
            recs = self.records()
            self.assertEqual(adapter.select(recs), parity_sample(recs))
        with self.assertRaises(ValueError):
            OrBenchAdapter(Path("x"), split="bogus")


if __name__ == "__main__":
    unittest.main()
