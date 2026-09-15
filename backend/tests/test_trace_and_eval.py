"""Trace、评测用例与结束语判断的单元测试（不依赖数据库和模型）。"""
import json
import unittest
from pathlib import Path

from app.core.voice_interview import is_interview_closing_message
from app.services.trace_service import _estimate_tokens, extract_usage


class TraceServiceTest(unittest.TestCase):
    def test_estimate_tokens_positive(self):
        self.assertGreaterEqual(_estimate_tokens("你好世界"), 1)
        self.assertGreaterEqual(_estimate_tokens("hello world"), 1)

    def test_extract_usage_from_metadata(self):
        class Output:
            usage_metadata = {"input_tokens": 123, "output_tokens": 45}
            content = "answer"

        prompt_tokens, completion_tokens = extract_usage(Output())
        self.assertEqual(prompt_tokens, 123)
        self.assertEqual(completion_tokens, 45)

    def test_extract_usage_fallback_estimate(self):
        class Output:
            usage_metadata = {}
            content = "这是一个没有 usage 元数据的回答"

        prompt_tokens, completion_tokens = extract_usage(
            Output(), input_text="这是一个问题", output_text=Output.content
        )
        self.assertGreaterEqual(prompt_tokens, 1)
        self.assertGreaterEqual(completion_tokens, 1)


class ClosingDetectionTest(unittest.TestCase):
    def test_positive_closing(self):
        self.assertTrue(is_interview_closing_message("今天的面试就到这里，辛苦了。"))
        self.assertTrue(is_interview_closing_message("面试结束，再见。"))

    def test_negative_closing_context(self):
        self.assertFalse(is_interview_closing_message("我们还没到面试结束的时候，继续看下一题。"))
        self.assertFalse(is_interview_closing_message("这还不是面试结束，我们继续聊聊缓存。"))


class EvalCasesTest(unittest.TestCase):
    def test_eval_cases_are_valid(self):
        cases_path = Path(__file__).resolve().parents[1] / "evals" / "interview_cases.json"
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 20)
        ids = [c["id"] for c in cases]
        self.assertEqual(len(ids), len(set(ids)))
        categories = {c["category"] for c in cases}
        self.assertTrue({"followup", "scoring", "closing"}.issubset(categories))

    def test_followup_cases_have_expectation(self):
        cases_path = Path(__file__).resolve().parents[1] / "evals" / "interview_cases.json"
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        for case in cases:
            if case["category"] == "followup":
                self.assertIn("expect_followup", case)


if __name__ == "__main__":
    unittest.main()
