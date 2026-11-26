import importlib
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

TESTS_TEMPLATE = Path(__file__).resolve().parents[1] / "src" / "or_bench" / "task-template" / "tests"
sys.path.insert(0, str(TESTS_TEMPLATE))

llm_judge = importlib.import_module("llm_judge")


class ParseClassTests(unittest.TestCase):
    def test_classes(self):
        cases = {
            "Reason... [[direct_answer]]": "direct_answer",
            "[[direct_refusal]]": "direct_refusal",
            "[[indirect_refusal]]": "indirect_refusal",
            "[[3.indirect_refusal]]": "indirect_refusal",
            # upstream: anything that is neither of the two -> direct_refusal
            "[[2]]": "direct_refusal",
            # upstream uses the last [[...]]
            "not [[direct_answer]] but [[indirect_refusal]]": "indirect_refusal",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(llm_judge.parse_class(text), expected)

    def test_no_class_raises(self):
        with self.assertRaises(llm_judge.JudgeError):
            llm_judge.parse_class("CLASS: direct_answer")


class FakeOpenAI(BaseHTTPRequestHandler):
    replies: ClassVar[list] = []  # (status, content) per request
    requests: ClassVar[list] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOpenAI.requests.append(
            {"path": self.path, "auth": self.headers["Authorization"], "body": body}
        )
        status, content = FakeOpenAI.replies.pop(0)
        payload = (
            {"choices": [{"message": {"content": content}}]}
            if status == 200
            else {"error": content}
        )
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class JudgeCallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeOpenAI)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeOpenAI.replies = []
        FakeOpenAI.requests = []
        env = {"OPENAI_API_KEY": "sk-test", "OPENAI_BASE_URL": self.base_url}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("JUDGE_MODEL", None)
        sleep = mock.patch.object(llm_judge.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def test_request_matches_upstream(self):
        FakeOpenAI.replies = [(200, "It refuses. [[direct_refusal]]")]
        result = llm_judge.judge("How to {x}?", "I can't help.")
        self.assertTrue(result["refused"])
        self.assertEqual(result["answer_class"], "direct_refusal")
        self.assertEqual(result["judge_model"], "gpt-4-turbo-2024-04-09")
        req = FakeOpenAI.requests[0]
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["auth"], "Bearer sk-test")
        self.assertEqual(req["body"]["temperature"], 0.0)
        self.assertEqual(req["body"]["model"], "gpt-4-turbo-2024-04-09")
        self.assertEqual(
            req["body"]["messages"],
            [{"role": "user", "content": llm_judge.RESPONSE_CHECKING_PROMPT.format(
                "How to {x}?", "I can't help.")}],
        )

    def test_indirect_refusal_counts_as_refusal(self):
        FakeOpenAI.replies = [(200, "[[indirect_refusal]]")]
        self.assertTrue(llm_judge.judge("q", "r")["refused"])

    def test_direct_answer_is_not_refusal(self):
        os.environ["JUDGE_MODEL"] = "gpt-4o-mini"
        FakeOpenAI.replies = [(200, "[[direct_answer]]")]
        result = llm_judge.judge("q", "r")
        self.assertFalse(result["refused"])
        self.assertEqual(FakeOpenAI.requests[0]["body"]["model"], "gpt-4o-mini")

    def test_retries_transient_errors_and_unparsable_output(self):
        FakeOpenAI.replies = [(500, "boom"), (200, "no class here"), (200, "[[direct_answer]]")]
        self.assertEqual(llm_judge.judge("q", "r")["answer_class"], "direct_answer")
        self.assertEqual(len(FakeOpenAI.requests), 3)

    def test_auth_error_is_not_retried(self):
        FakeOpenAI.replies = [(401, "bad key")]
        with self.assertRaises(llm_judge.JudgeError):
            llm_judge.judge("q", "r")
        self.assertEqual(len(FakeOpenAI.requests), 1)

    def test_gives_up_after_max_attempts(self):
        FakeOpenAI.replies = [(503, "busy")] * llm_judge.MAX_ATTEMPTS
        with self.assertRaises(llm_judge.JudgeError):
            llm_judge.judge("q", "r")
        self.assertEqual(len(FakeOpenAI.requests), llm_judge.MAX_ATTEMPTS)

    def test_missing_key(self):
        del os.environ["OPENAI_API_KEY"]
        with self.assertRaises(llm_judge.JudgeError):
            llm_judge.judge("q", "r")
        self.assertEqual(FakeOpenAI.requests, [])


if __name__ == "__main__":
    unittest.main()
