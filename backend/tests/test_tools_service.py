"""Agent 工具层单元测试（不依赖数据库和模型）。"""
import asyncio
import unittest

from app.services.tools_service import _job_skill_lookup, _question_bank_lookup, list_tools


class ToolsServiceTest(unittest.TestCase):
    def test_tool_schema(self):
        tools = list_tools()
        names = {t["name"] for t in tools}
        self.assertIn("job_skill_lookup", names)
        self.assertIn("company_info_lookup", names)
        self.assertIn("question_bank_lookup", names)
        for tool in tools:
            self.assertIn("description", tool)
            self.assertEqual(tool["parameters"]["type"], "object")

    def test_job_skill_lookup(self):
        result = asyncio.run(
            _job_skill_lookup(
                {"job_description": "要求熟悉 Python、FastAPI、PostgreSQL、Redis 和 LangGraph"}
            )
        )
        skills = result["skills"]
        self.assertIn("Python", skills)
        self.assertIn("FastAPI", skills)
        self.assertIn("Redis", skills)
        self.assertIn("LangGraph", skills)

    def test_question_bank_lookup(self):
        result = asyncio.run(_question_bank_lookup({"topic": "redis", "limit": 3}))
        self.assertTrue(result["knowledge_points"])
        self.assertTrue(result["candidate_questions"])
        self.assertLessEqual(len(result["candidate_questions"]), 6)


if __name__ == "__main__":
    unittest.main()
