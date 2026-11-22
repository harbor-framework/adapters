from __future__ import annotations

import unittest

from makemesay.core import run_auto_eval
from makemesay.scoring import ensure_nltk_resources, mentions_codeword


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_nltk_resources()

    def test_codeword_matching_matches_plural_and_curly_quote_handling(self) -> None:
        self.assertTrue(mentions_codeword("I read the “books” yesterday.", "book"))
        self.assertFalse(mentions_codeword("I read a bookshelf yesterday.", "book"))


class GameLoopTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_nltk_resources()

    async def test_role_order_visibility_and_judge_call_order(self) -> None:
        calls: list[tuple[str, list[dict[str, str]]]] = []

        async def manipulatee(messages: list[dict[str, str]]) -> str:
            calls.append(("manipulatee", messages))
            return "Hi, how are you?" if len(calls) == 1 else "I think no word was chosen."

        async def manipulator(messages: list[dict[str, str]]) -> str:
            calls.append(("manipulator", messages))
            return "I have been enjoying the weather."

        async def judge(messages: list[dict[str, str]]) -> str:
            calls.append(("judge", messages))
            return "0"

        game = await run_auto_eval(
            codeword="comet",
            manipulator_completion_fn=manipulator,
            manipulatee_completion_fn=manipulatee,
            judge_completion_fn=judge,
            max_turns=2,
        )

        self.assertEqual([name for name, _ in calls], ["manipulatee", "manipulator", "manipulatee"])
        self.assertEqual(game.turn, 2)
        self.assertEqual(game.messages[-1].name, game.manipulatee.id)
        self.assertTrue(any(message["role"] == "system" for message in calls[1][1]))
        self.assertEqual(await game.is_win(), False)
        self.assertEqual(await game.is_loss(), True)
        self.assertEqual(await game.is_user_aware_of_manipulation(), False)
        self.assertEqual(game.judge_responses, ["0", "0", "0"])


if __name__ == "__main__":
    unittest.main()
