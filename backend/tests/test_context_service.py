"""上下文压缩与 Token 估算单元测试。"""
import unittest

from app.services.context_service import compress_messages, estimate_tokens, trim_history


class ContextServiceTest(unittest.TestCase):
    def test_estimate_tokens_positive(self):
        self.assertGreaterEqual(estimate_tokens("你好世界"), 1)
        self.assertGreaterEqual(estimate_tokens(""), 1)

    def test_compress_keeps_recent_messages(self):
        messages = [
            {"role": "assistant", "content": f"第{i}题"} for i in range(20)
        ]
        result = compress_messages(messages, max_tokens=30, keep_last=4)
        self.assertLessEqual(len(result), 4)
        self.assertEqual(result[-1]["content"], "第19题")

    def test_trim_history_limits_pairs_and_chars(self):
        history = [
            {"question": f"问题{i}", "answer": f"回答{i}"} for i in range(10)
        ]
        result = trim_history(history, max_chars=80, keep_pairs=3)
        self.assertLessEqual(len(result), 3)
        total = sum(len(p["question"]) + len(p["answer"]) for p in result)
        self.assertLessEqual(total, 80 + 200)


if __name__ == "__main__":
    unittest.main()