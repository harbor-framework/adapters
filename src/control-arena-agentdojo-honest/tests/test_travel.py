import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import text_content_block_from_string

from control_arena_agentdojo_honest.adapter import (
    CAR_LOOKUPS, CASES, RESTAURANT_LOOKUPS, ControlArenaAgentdojoHonestAdapter,
)


class TravelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = tempfile.TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.root = Path(work.name)
        cls.paths = ControlArenaAgentdojoHonestAdapter(cls.root).run()
        cls.suite = get_suite("v1.2.1", "travel")
        cls.env = cls.suite.load_and_inject_default_environment({})

    def test_honest_questions_and_canonical_verdicts(self):
        self.assertEqual(len(self.paths), 4)
        for path in self.paths:
            task_id = json.loads((path / "tests/case.json").read_bytes())["user_task_id"]
            task = self.suite.get_user_task_by_id(task_id)
            grader = runpy.run_path(str(path / "tests/grade.py"))["utility"]
            self.assertIn(task.PROMPT, (path / "instruction.md").read_text("utf-8"))
            oracle = (path / "solution/answer.txt").read_text("utf-8")
            for answer, expect in [(oracle, True), ("", False), ("An unrelated answer.", False)]:
                original = self.suite._check_task_result(task, [text_content_block_from_string(answer)], self.env, self.env.model_copy(deep=True), [])
                self.assertEqual(original, expect)
                self.assertEqual(grader(task_id, answer), original)
            self.assertFalse((path / "environment/answer.txt").exists())
            self.assertNotIn(oracle, (path / "instruction.md").read_text("utf-8"))

    def test_each_lookup_matches_the_simulated_environment(self):
        for slug, methods, fixture, records, city in [
            ("travel-user-task-9", RESTAURANT_LOOKUPS, self.env.restaurants, self.env.restaurants.restaurant_list, "Paris"),
            ("travel-user-task-13", CAR_LOOKUPS, self.env.car_rental, self.env.car_rental.company_list, "Los Angeles"),
        ]:
            directory = self.root / slug / "environment"
            names = [row.name for row in records if row.city == city][:3]
            for method in methods:
                city_listing = method.__name__.startswith("get_all_")
                values = [city] if city_listing else names
                p = subprocess.run([sys.executable, "-X", "utf8", str(directory / "lookup.py"), method.__name__, *values],
                                   capture_output=True, check=True)
                self.assertEqual(json.loads(p.stdout), method(fixture, city if city_listing else names))
            bad = subprocess.run([sys.executable, str(directory / "lookup.py"), "reserve_hotel", "example"],
                                 capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(bad.stdout, b"")

    def test_selection_and_allowlist(self):
        name = next(iter(CASES))
        adapter = ControlArenaAgentdojoHonestAdapter(self.root, task_ids=["control-arena/" + name], overwrite=True)
        self.assertEqual(adapter.run(), [self.root / name])
        with self.assertRaises(ValueError):
            ControlArenaAgentdojoHonestAdapter(self.root, task_ids=["travel-user-task-99"]).run()
