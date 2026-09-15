"""升级项回归测试：管理员权限、告警阈值和规划工具注入。"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api import admin_deps
from app.core import interview_planner
from scripts.check_alerts import build_alerts


class AdminDependencyTest(unittest.IsolatedAsyncioTestCase):
    async def test_require_admin_rejects_regular_user(self):
        with patch.object(
            admin_deps.human_review_service,
            "is_admin",
            new=AsyncMock(return_value=False),
        ):
            with self.assertRaises(HTTPException) as context:
                await admin_deps.require_admin({"sub": "12"})
        self.assertEqual(context.exception.status_code, 403)

    async def test_require_admin_accepts_admin(self):
        with patch.object(
            admin_deps.human_review_service,
            "is_admin",
            new=AsyncMock(return_value=True),
        ):
            payload = await admin_deps.require_admin({"sub": "12"})
        self.assertEqual(payload["sub"], "12")


class AlertThresholdTest(unittest.TestCase):
    def test_build_alerts_reports_success_rate(self):
        args = SimpleNamespace(
            min_runs=3,
            min_success_rate=0.95,
            max_p95_ms=8000,
            max_open_failures=20,
            min_feedback=5,
            min_avg_rating=3.5,
            max_low_ratings=3,
        )
        alerts = build_alerts(
            {
                "total_runs": 10,
                "success_rate": 0.8,
                "p95_latency_ms": 1000,
            },
            {
                "open_eval_failures": 0,
                "feedback_total": 0,
                "feedback_avg_rating": 0,
                "feedback_low_rating": 0,
            },
            args,
        )
        self.assertTrue(any("成功率过低" in item for item in alerts))


class PlannerToolIntegrationTest(unittest.TestCase):
    def test_planner_injects_job_skill_tool_context(self):
        class FakeLLM:
            prompt = ""

            async def ainvoke(self, prompt):
                self.prompt = prompt
                return SimpleNamespace(
                    content='[{"id": 1, "topic": "Python", "content": "请介绍 Python", "type": "tech"}]'
                )

        fake_llm = FakeLLM()
        invoke_result = {
            "success": True,
            "result": {"skills": ["Python", "FastAPI", "PostgreSQL"]},
        }
        with patch(
            "app.core.interview_planner.llms.get_llm_for_request",
            return_value=fake_llm,
        ), patch(
            "app.services.tools_service.invoke_tool",
            new=AsyncMock(return_value=invoke_result),
        ), patch(
            "app.services.rag_service.retrieve_knowledge",
            new=AsyncMock(return_value=[]),
        ), patch(
            "app.services.rag_service.format_knowledge",
            return_value="",
        ):
            plan = asyncio.run(
                interview_planner.generate_interview_plan(
                    resume="候选人有后端开发经验",
                    job_description="要求熟悉 Python、FastAPI、PostgreSQL",
                    company_info="未知",
                    max_questions=1,
                    api_config={},
                    session_id="test-session",
                )
            )

        self.assertEqual(len(plan), 1)
        self.assertIn("岗位技能工具结果", fake_llm.prompt)
        self.assertIn("FastAPI", fake_llm.prompt)


if __name__ == "__main__":
    unittest.main()
