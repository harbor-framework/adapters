import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from git import Repo

from control_arena_vllm_honest import sources
from control_arena_vllm_honest.adapter import ControlArenaVllmHonestAdapter


def simulated_reset(raw):
    # Test only the two authenticated upstream snippets. Candidate submissions are never executed.
    if sources.digest(raw) not in {sources.BASE_SHA, sources.GOLD_SHA}:
        raise ValueError("Simulation requires a pinned upstream file")
    classes = {node.name: node for node in ast.parse(raw).body if isinstance(node, ast.ClassDef)}
    methods = [n for n in classes["LoggingStatLogger"].body if isinstance(n, ast.FunctionDef) and n.name in ("__init__", "_reset")]
    namespace = {"time": time, "SchedulerStats": SimpleNamespace, "PrefixCachingMetrics": SimpleNamespace}
    for method in methods:
        exec(compile(ast.Module(body=[method], type_ignores=[]), "<trusted upstream logger>", "exec"), namespace)
    logger = type("IntervalLogger", (), {f.name: namespace[f.name] for f in methods})()
    window = logger.prefix_caching_metrics
    window.hit_rate = 0.75
    logger.num_prompt_tokens.append(20)
    logger.num_generation_tokens.append(10)
    logger._reset(100)
    return logger, window, classes["PrometheusStatLogger"]


class MetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.cache = Path(os.environ.get("VLLM_METRICS_SOURCE_CACHE", ".cache/control-arena-vllm-honest"))
        (cls.task,) = ControlArenaVllmHonestAdapter(cls.root / "tasks", cls.cache).run()
        sys.path.insert(0, str(cls.task / "tests"))
        cls.addClassCleanup(sys.path.pop, 0)
        import grade
        cls.grade = grade
        cls.baseline = (cls.task / "environment" / "loggers.py").read_bytes()
        cls.reference = (cls.task / "solution" / "loggers.py").read_bytes()
        cls.case = json.loads((cls.task / "tests" / "case.json").read_bytes())

    def test_existing_destinations(self):
        source = self.task
        root = self.root / "destinations"
        root.mkdir()
        path = root / source.name

        def run(overwrite):
            return ControlArenaVllmHonestAdapter(root, source_cache=self.cache, task_ids=[source.name], overwrite=overwrite).run()

        def rejected():
            for overwrite in (False, True):
                with self.subTest(overwrite=overwrite), self.assertRaises(ValueError):
                    run(overwrite)

        path.write_text("keep")
        rejected()
        self.assertEqual(path.read_text(), "keep")
        path.unlink()
        path.mkdir()
        (path / "keep").write_text("original")
        rejected()
        self.assertEqual((path / "keep").read_text(), "original")
        shutil.rmtree(path)
        shutil.copytree(source, path)
        marker = path / "tests" / "case.json"
        previous = json.loads(marker.read_bytes())
        marker.write_text("{}", encoding="utf-8")
        rejected()
        self.assertEqual(marker.read_text(), "{}")
        marker.write_text(json.dumps({**previous, "older_format_note": True}), encoding="utf-8")
        self.assertEqual(run(False), [path])
        self.assertIn("older_format_note", json.loads(marker.read_bytes()))
        self.assertEqual(run(True), [path])
        self.assertEqual(json.loads(marker.read_bytes()), previous)
        shutil.rmtree(path)
        try:
            path.symlink_to(source, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(path), str(source)],
                           check=True, capture_output=True)
        rejected()
        self.assertTrue(path.is_symlink() or path.is_junction())
        self.assertTrue((source / "instruction.md").is_file())

    def test_source_identity_and_private_solution(self):
        self.assertEqual(sources.digest(self.baseline), sources.BASE_SHA)
        self.assertEqual(sources.digest(self.reference), sources.GOLD_SHA)
        self.assertIn(self.case["prompt"], (self.task / "instruction.md").read_text("utf-8"))
        self.assertEqual({p.name for p in (self.task / "environment").iterdir()}, {"loggers.py", "LICENSE", "Dockerfile"})
        with self.assertRaisesRegex(ValueError, "Only the pinned"):
            ControlArenaVllmHonestAdapter(self.root, self.cache, task_ids=["another-task"]).run()
        corrupt = self.root / "corrupt"
        shutil.copytree(self.cache, corrupt)
        (corrupt / "baseline.py").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            sources.materialize(corrupt)

    def test_counter_lifetime_across_intervals(self):
        baseline, old, prom_before = simulated_reset(self.baseline)
        reference, window, prom_after = simulated_reset(self.reference)
        self.assertIsNot(baseline.prefix_caching_metrics, old)
        self.assertIs(reference.prefix_caching_metrics, window)
        self.assertEqual(reference.prefix_caching_metrics.hit_rate, 0.75)
        for logger in (baseline, reference):
            self.assertEqual((logger.num_prompt_tokens, logger.num_generation_tokens, logger.last_log_time), ([], [], 100))
        self.assertEqual(ast.dump(prom_before), ast.dump(prom_after))

    def test_diff_matches_native_git_command(self):
        repo_dir = self.root / "source-repo"
        repo = Repo.init(repo_dir)
        file = repo_dir / sources.SOURCE
        file.parent.mkdir(parents=True)
        file.write_bytes(self.baseline)
        repo.git.add("--all")
        baseline_tree = repo.git.write_tree()
        file.write_bytes(self.reference)
        repo.git.add("--all")
        original = repo.git(c="core.fileMode=false").diff(baseline_tree, "--cached")
        self.assertEqual(self.grade.code_diff(self.baseline, self.reference), original)
        self.assertEqual(self.grade.code_diff(self.baseline, self.baseline), "")

    def test_native_grading_positive_negative_missing(self):
        for name, candidate, expected in (("reference", self.reference, 1), ("unchanged", self.baseline, 0), ("missing", None, 0)):
            with self.subTest(name=name):
                verdict, _ = self.grade.evaluate(self.case, self.baseline, candidate, self.grade.FIXTURE, self.root / name)
                self.assertEqual(verdict, expected)
        with self.assertRaisesRegex(ValueError, "fixture recognizes"):
            self.grade.evaluate(self.case, self.baseline, self.baseline + b"\n", self.grade.FIXTURE, self.root / "unknown")


if __name__ == "__main__":
    unittest.main()
