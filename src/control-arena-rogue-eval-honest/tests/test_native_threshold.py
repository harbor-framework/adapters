import unittest

from control_arena.settings.rogue_eval.prompts import SETTING_DESCRIPTION
from control_arena.settings.rogue_eval.scorer import USEFULNESS_THRESHOLD, _evaluate_main_task
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import CORRECT, INCORRECT

from control_arena_rogue_eval_honest.adapter import TASK
from control_arena_rogue_eval_honest.fixture_data import ORACLE, STDOUT, recorded_judge


class NativeThresholdTest(unittest.IsolatedAsyncioTestCase):
    async def test_native_passing_boundary(self):
        judge = recorded_judge(SETTING_DESCRIPTION, TASK)
        verdict = await _evaluate_main_task(SETTING_DESCRIPTION, TASK, ORACLE, STDOUT, "", USEFULNESS_THRESHOLD, judge)
        self.assertEqual(CORRECT, verdict.value)

        model_id = "mockllm/addition-threshold-74"
        response = "<reasoning>Recorded boundary test.</reasoning><usefulness_score>74</usefulness_score>"
        below = get_model(model_id, custom_outputs=[ModelOutput.from_content(model_id, response)])
        verdict = await _evaluate_main_task(SETTING_DESCRIPTION, TASK, ORACLE, STDOUT, "", USEFULNESS_THRESHOLD, below)
        self.assertEqual(INCORRECT, verdict.value)
