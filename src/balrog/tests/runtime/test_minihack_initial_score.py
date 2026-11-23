"""Initial MiniHack progression compatibility and narrowly scoped guard tests."""
from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime_support import PACKAGE, configure_upstream, game_server

UPSTREAM = configure_upstream()
from balrog.environments.nle.progress import BaseProgress

Episode = game_server().Episode


def stub_environment(stats, progress):
    return SimpleNamespace(get_stats=lambda: dict(stats),
                           env=SimpleNamespace(gym_env=SimpleNamespace(env=SimpleNamespace(progress=progress))))


class InitialProgressGuardTest(unittest.TestCase):
    def setUp(self):
        self.episode = object.__new__(Episode)
        self.episode.env_name = "minihack"
        self.episode.transitions = []

    def test_reads_actual_native_class_attribute_without_inventing_zero(self):
        progress = BaseProgress()
        self.assertEqual(progress.__dict__, {})
        with patch.object(BaseProgress, "progression", 0.375):
            self.assertEqual(self.episode._native_progression(stub_environment({}, progress)), 0.375)
        self.assertEqual(progress.__dict__, {})

    def test_present_native_stat_takes_precedence(self):
        self.assertEqual(self.episode._native_progression(
            stub_environment({"progression": 0.25}, object())), 0.25)

    def test_missing_progression_after_an_action_remains_an_error(self):
        self.episode.transitions = [{"step": 0}]
        with self.assertRaises(KeyError):
            self.episode._native_progression(stub_environment({}, BaseProgress()))

    def test_missing_progression_for_other_environments_remains_an_error(self):
        for name in ("babyai", "babaisai", "crafter", "nle", "textworld"):
            with self.subTest(env_name=name):
                self.episode.env_name = name
                with self.assertRaises(KeyError):
                    self.episode._native_progression(stub_environment({}, BaseProgress()))

    def test_unexpected_native_progress_class_remains_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "Unexpected MiniHack progress object"):
            self.episode._native_progression(stub_environment({}, SimpleNamespace(progression=0.0)))


class NativeInitialScoreTest(unittest.TestCase):
    def test_real_zero_action_episode_and_fresh_replay_return_native_zero(self):
        manifest = json.loads((PACKAGE / "fixtures/minihack_manifest.json").read_text())
        case = next(c for c in manifest["cases"]
                    if c["episode"]["task_id"] == "minihack-boxoban-medium-v0-seed-0")
        episode = Episode(case["episode"], UPSTREAM / "balrog/config/config.yaml")
        try:
            self.assertEqual(episode.env.get_stats(), {})
            result = episode.result()
            self.assertEqual(result["steps"], 0)
            self.assertEqual(result["transitions"], [])
            self.assertEqual(result["progression"], 0.0)
            self.assertEqual(result["replay_progression"], 0.0)
            self.assertTrue(result["replay_verified"])
            self.assertFalse(result["terminated"])
            self.assertFalse(result["truncated"])
            self.assertEqual(episode.result(), result)
        finally:
            episode.close()


if __name__ == "__main__":
    unittest.main()
