"""Exercise production Episode.result failure classification without sockets/APIs."""

import copy
import threading
import unittest

from runtime_support import configure_upstream, game_server

configure_upstream()
server = game_server()


class Simulator:
    """Small simulator double; Episode.action/_advance/result are unmodified."""

    def __init__(self, score=2 / 22, text="after action", step_error=None):
        self.score = score
        self.text = text
        self.step_error = step_error
        self.closed = False

    def check_action_validity(self, action):
        return action

    def step(self, action):
        if self.step_error is not None:
            raise self.step_error
        return {"text": {"long_term_context": self.text}}, 0.0, False, False, {}

    def get_stats(self):
        return {"progression": self.score}

    def close(self):
        self.closed = True


class CrafterFailurePolicyTest(unittest.TestCase):
    def make_episode(self, replay, *, env_name="crafter", initial_text="initial"):
        # Only construction is replaced. Native stepping, recorded transitions,
        # independent replay and failure handling run through production code.
        episode = server.Episode.__new__(server.Episode)
        episode.lock = threading.RLock()
        episode.env_name = env_name
        episode.task_id = env_name + "-test-seed-0"
        episode.task = "test"
        episode.seed = 0
        episode.env = Simulator()
        episode.observation = {"text": {"long_term_context": "initial"}}
        episode.initial_hash = server.observation_hash(episode.observation)
        episode.mission = None
        episode.instruction = "test instructions"
        episode.max_steps = 2000
        episode.feedback = True
        episode.transitions = []
        episode.terminated = episode.truncated = episode.finalized = False
        episode._result = episode._failure = None
        episode._new_environment = lambda: (replay, {"text": {"long_term_context": initial_text}})
        episode.action("Noop", 0)
        self.addCleanup(episode.close)
        return episode

    def assert_infrastructure_failure(self, episode, replay, message):
        with self.assertRaisesRegex(RuntimeError, message):
            episode.result()
        self.assertIsNone(episode._result)
        self.assertIsNotNone(episode._failure)
        self.assertTrue(replay.closed)
        with self.assertRaisesRegex(RuntimeError, "Episode failed"):
            episode.result()

    def test_invalid_fresh_replay_scores_never_become_crafter_divergence(self):
        for score in (float("nan"), float("inf"), float("-inf"), -0.01, 1.01):
            with self.subTest(score=score):
                replay = Simulator(score=score)
                episode = self.make_episode(replay)
                self.assert_infrastructure_failure(episode, replay, "Invalid.*progression")

    def test_initial_observation_mismatch_is_not_crafter_fallback(self):
        replay = Simulator()
        episode = self.make_episode(replay, initial_text="wrong frozen instance")
        self.assert_infrastructure_failure(episode, replay, "Initial observation differs")

    def test_simulator_step_exception_is_not_crafter_fallback(self):
        replay = Simulator(step_error=RuntimeError("simulator step failed"))
        episode = self.make_episode(replay)
        self.assert_infrastructure_failure(episode, replay, "simulator step failed")

    def test_legal_crafter_trajectory_divergence_preserves_only_live_score(self):
        replay = Simulator(score=0.0, text="different creature state")
        episode = self.make_episode(replay)
        original_transitions = copy.deepcopy(episode.transitions)
        result = episode.result()
        self.assertEqual(result["progression"], 2 / 22)
        self.assertIs(result["replay_verified"], False)
        self.assertIsNone(result["replay_progression"])
        self.assertEqual(result["scoring_mode"], "authoritative_native_state")
        self.assertEqual(result["replay_diagnostic"]["code"], "crafter_native_object_order_nondeterminism")
        self.assertEqual(result["replay_diagnostic"]["first_divergent_step"], 0)
        self.assertEqual(result["transitions"], original_transitions)
        self.assertTrue(replay.closed)
        self.assertIsNone(episode._failure)

    def test_other_environments_cannot_use_crafter_divergence_policy(self):
        for name in ("babyai", "babaisai", "textworld", "nle", "minihack"):
            with self.subTest(env_name=name):
                replay = Simulator(text="different state")
                episode = self.make_episode(replay, env_name=name)
                self.assert_infrastructure_failure(episode, replay, "Replay differs")

    def test_matching_crafter_replay_remains_verified(self):
        replay = Simulator()
        episode = self.make_episode(replay)
        result = episode.result()
        self.assertIs(result["replay_verified"], True)
        self.assertEqual(result["scoring_mode"], "deterministic_replay")
        self.assertEqual(result["replay_progression"], result["progression"])
        self.assertIsNone(result["replay_diagnostic"])


if __name__ == "__main__":
    unittest.main()
