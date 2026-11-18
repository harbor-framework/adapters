"""Regression checks for fractional scores and native Baba reset diagnostics."""
import copy
import unittest

from runtime_support import TEMPLATE, configure_upstream, game_server, load_file, parity_runner

configure_upstream()
server = game_server()
runner = parity_runner()
verifier = load_file("_balrog_suite_verifier", TEMPLATE / "tests/verifier.py")


class SuiteVerificationTest(unittest.TestCase):
    @staticmethod
    def crafter_fallback():
        return {"schema_version": 1, "replay_verified": False, "finalized": True,
                "env_name": "crafter", "progression": 18/22, "replay_progression": None,
                "terminated": True, "truncated": False, "steps": 180, "max_steps": 2000,
                "transitions": [{} for _ in range(180)],
                "scoring_mode": "authoritative_native_state",
                "replay_diagnostic": {"code": "crafter_native_object_order_nondeterminism",
                                      "first_divergent_step": 49, "message": "Replay differs at step 49"}}

    def test_explicit_crafter_fallback_preserves_fractional_native_score(self):
        self.assertEqual(verifier.validate_result(self.crafter_fallback()), 18/22)

    def test_crafter_fallback_cannot_relax_other_environments(self):
        for env_name in ("babyai", "babaisai", "textworld", "minihack", "nle"):
            with self.subTest(env_name=env_name):
                result = self.crafter_fallback()
                result["env_name"] = env_name
                with self.assertRaises(ValueError):
                    verifier.validate_result(result)

    def test_crafter_fallback_requires_all_explicit_evidence_fields(self):
        for key in ("env_name", "replay_verified", "replay_progression", "scoring_mode", "replay_diagnostic"):
            with self.subTest(missing=key):
                result = self.crafter_fallback()
                del result[key]
                with self.assertRaises(ValueError):
                    verifier.validate_result(result)
        for key in ("code", "first_divergent_step"):
            with self.subTest(missing_diagnostic=key):
                result = self.crafter_fallback()
                del result["replay_diagnostic"][key]
                with self.assertRaises(ValueError):
                    verifier.validate_result(result)

    def test_crafter_fallback_rejects_invalid_native_scores(self):
        for score in (float("nan"), float("inf"), -0.1, 1.01, True, "0.5", None):
            with self.subTest(score=score):
                result = self.crafter_fallback()
                result["progression"] = score
                with self.assertRaises(ValueError):
                    verifier.validate_result(result)

    def test_crafter_fallback_rejects_ambiguous_or_invalid_replay_evidence(self):
        for key, value in (("scoring_mode", "deterministic_replay"), ("replay_progression", 18/22),
                           ("replay_verified", None)):
            with self.subTest(field=key, value=value):
                result = self.crafter_fallback()
                result[key] = value
                with self.assertRaises(ValueError):
                    verifier.validate_result(result)
        for divergence in (-1, 181, True, 0.5, "49", None):
            with self.subTest(divergence=divergence):
                result = self.crafter_fallback()
                result["replay_diagnostic"]["first_divergent_step"] = divergence
                with self.assertRaises(ValueError):
                    verifier.validate_result(result)
        result = self.crafter_fallback()
        result["replay_diagnostic"]["code"] = "generic_runtime_failure"
        with self.assertRaises(ValueError):
            verifier.validate_result(result)

    def test_known_reset_addresses_do_not_break_replay_or_change_prompt(self):
        text = ("[...] IS YOU rule was broken, environment reset "
                "<function BabaIsAIWrapper.textworld_process_obsv.<locals>.<lambda> at 0x1234> "
                "<PIL.Image.Image image mode=RGB size=416x288 at 0x5678>")
        first = {"text": {"long_term_context": text, "short_term_context": ""}}
        second = copy.deepcopy(first)
        second["text"]["long_term_context"] = text.replace("0x1234", "0xAAAA").replace("0x5678", "0xBBBB")
        before = copy.deepcopy(first)
        self.assertEqual(server.observation_hash(first), server.observation_hash(second))
        self.assertEqual(server.observation_hash(first), runner.observed_hash(second))
        self.assertEqual(first, before)
        changed = copy.deepcopy(second)
        changed["text"]["long_term_context"] += "wall is win"
        self.assertNotEqual(server.observation_hash(first), server.observation_hash(changed))

    def test_arbitrary_hex_text_is_never_discarded(self):
        first = {"text": {"long_term_context": "door at 0x1234"}}
        second = {"text": {"long_term_context": "door at 0x5678"}}
        self.assertNotEqual(server.observation_hash(first), server.observation_hash(second))

    def test_partial_progress_before_termination_is_valid_outside_babyai(self):
        result = {"schema_version": 1, "replay_verified": True, "finalized": True,
                  "env_name": "crafter", "progression": 2/22, "replay_progression": 2/22,
                  "terminated": False, "truncated": False, "steps": 1, "max_steps": 2000,
                  "transitions": [{}]}
        self.assertEqual(verifier.validate_result(result), 2/22)
        result["env_name"] = "babyai"
        with self.assertRaises(ValueError):
            verifier.validate_result(result)


if __name__ == "__main__":
    unittest.main()
