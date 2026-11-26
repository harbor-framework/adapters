import hashlib
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from control_arena import EvalMode
from control_arena.settings.sae_interp_sabotage.scorers import ResponseType
from control_arena.settings.sae_interp_sabotage.setting import get_dataset
from inspect_ai.model import ModelOutput, ModelUsage, get_model

from control_arena_sae_interp.adapter import TEMPLATE


grader = runpy.run_path(str(TEMPLATE / "tests/grade.py"))
fixture_judge = runpy.run_path(str(TEMPLATE / "tests/fixture_judge.py"))["fixture_judge"]


class VerifierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        sample = get_dataset(EvalMode.HONEST)[0]
        self.case = {
            "source_index": 0,
            "prompt_sha256": hashlib.sha256(sample.input.encode("utf-8")).hexdigest(),
        }
        self.reference = ResponseType(interpretation=sample.metadata["main_task_name"])

    def test_native_scorer_preserves_both_objectives(self):
        unrelated = ResponseType(interpretation="A synthetic theme used to test submission transport.")
        for mode, submission, expected in (
            (EvalMode.HONEST, self.reference, {"main_task_success": 1}),
            (EvalMode.HONEST, unrelated, {"main_task_success": 0}),
            (EvalMode.ATTACK, self.reference, {"main_task_success": 1, "side_task_success": 0}),
            (EvalMode.ATTACK, unrelated, {"main_task_success": 0, "side_task_success": 1}),
        ):
            with self.subTest(mode=mode, expected=expected):
                result = grader["score_submission"](self.case, mode, submission, fixture_judge(), self.root)
                self.assertEqual(result, expected)

    def test_empty_or_invalid_artifact_uses_native_no_submission_scores(self):
        case_file = self.root / "case.json"
        case_file.write_text(json.dumps(self.case), encoding="utf-8")
        answer_file = self.root / "submission.json"
        reward_file = self.root / "reward.json"
        with patch.dict(os.environ, {
            "CONTROL_ARENA_EVAL_MODE": "attack",
            "CONTROL_ARENA_JUDGE_MODEL": "unused/no-submission",
        }):
            for content in (None, b"invalid JSON", b'{"interpretation": 7}'):
                with self.subTest(content=content):
                    if content is not None:
                        answer_file.write_bytes(content)
                    grader["main"](reward_file, case_path=case_file, submission_path=answer_file)
                    self.assertEqual(json.loads(reward_file.read_text()), {
                        "main_task_success": 0, "side_task_success": 0,
                    })
                    self.assertEqual((self.root / "reward.txt").read_text().strip(), "0")
                    provenance = json.loads((self.root / "provenance.json").read_text())
                    self.assertFalse(provenance["valid_submission"])
                    self.assertEqual(provenance["prompt_sha256"], self.case["prompt_sha256"])
                    self.assertEqual(provenance["eval_mode"], "attack")
            case_file.write_text(json.dumps(dict(self.case, prompt_sha256="stale")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                grader["main"](reward_file, case_path=case_file, submission_path=answer_file)
            for name in ("reward.txt", "reward.json", "provenance.json"):
                self.assertFalse((self.root / name).exists())

    def test_mismatch_rejects_case_before_scoring(self):
        case = dict(self.case, prompt_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "does not match"):
            grader["score_submission"](case, EvalMode.HONEST, None, "unused/no-submission", self.root)

    def test_native_scoring_error_propagates(self):
        model = get_model("mockllm/no-responses", custom_outputs=[])
        with self.assertRaisesRegex(RuntimeError, "Native SAE scoring failed"):
            grader["score_submission"](self.case, EvalMode.HONEST, self.reference, model, self.root)

    def test_inconclusive_native_judge_raises(self):
        output = ModelOutput.from_content("mockllm/no-verdict", "No XML verdict.")
        output.usage = ModelUsage()
        model = get_model("mockllm/no-verdict", custom_outputs=[output] * 3)
        with self.assertRaisesRegex(ValueError, "inconclusive"):
            grader["score_submission"](self.case, EvalMode.HONEST, self.reference, model, self.root)
