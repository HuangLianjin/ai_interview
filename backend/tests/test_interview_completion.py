import unittest
import sys
import types


# 进度与路由测试不需要加载真实 LLM、数据库和 LangGraph 依赖。
langchain_core_stub = types.ModuleType("langchain_core")
langchain_messages_stub = types.ModuleType("langchain_core.messages")


class _Message:
    def __init__(self, content="", **_kwargs):
        self.content = content


langchain_messages_stub.HumanMessage = _Message
langchain_messages_stub.AIMessage = _Message
langchain_messages_stub.SystemMessage = _Message
langchain_messages_stub.BaseMessage = _Message
sys.modules.setdefault("langchain_core", langchain_core_stub)
sys.modules.setdefault("langchain_core.messages", langchain_messages_stub)

langgraph_stub = types.ModuleType("langgraph")
langgraph_graph_stub = types.ModuleType("langgraph.graph")
langgraph_graph_stub.END = "__end__"


class _StateGraph:
    def __init__(self, *_args, **_kwargs):
        pass


langgraph_graph_stub.StateGraph = _StateGraph
sys.modules.setdefault("langgraph", langgraph_stub)
sys.modules.setdefault("langgraph.graph", langgraph_graph_stub)

llms_stub = types.ModuleType("app.core.llms")
llms_stub.get_async_omni_client = lambda _api_config: None
llms_stub.get_llm_for_request = lambda *_args, **_kwargs: None
sys.modules.setdefault("app.core.llms", llms_stub)

session_service_stub = types.ModuleType("app.database.session_service")
session_service_stub.SessionService = object
sys.modules.setdefault("app.database.session_service", session_service_stub)

memory_stub = types.ModuleType("app.core.memory")


async def _get_async_sqlite_saver():
    return None


memory_stub.get_async_sqlite_saver = _get_async_sqlite_saver
sys.modules.setdefault("app.core.memory", memory_stub)

mode_strategy_stub = types.ModuleType("app.core.mode_strategy")
mode_strategy_stub.ModeStrategyFactory = object
sys.modules.setdefault("app.core.mode_strategy", mode_strategy_stub)

from app.core.graph import END, route_after_responder
from app.core.voice_interview import calculate_interview_progress, is_interview_closing_message


class VoiceInterviewProgressTest(unittest.TestCase):
    def setUp(self):
        self.plan = [
            {
                "topic": "项目经历",
                "content": "请介绍一个你最近负责的项目。",
            },
            {
                "topic": "系统设计",
                "content": "请说明你会如何设计一个高并发缓存系统。",
            },
        ]

    def test_last_question_follow_ups_do_not_complete_without_closing(self):
        """最后一题追问多次时，未明确结束不能标记完成。"""
        history = [
            {"role": "assistant", "content": "第一个问题，请介绍一个你最近负责的项目。"},
            {"role": "user", "content": "我做过一个订单系统。"},
            {"role": "assistant", "content": "第二个问题，请说明你会如何设计一个高并发缓存系统。"},
            {"role": "user", "content": "我会使用 Redis。"},
            {"role": "assistant", "content": "能继续说明缓存一致性怎么保障吗？"},
            {"role": "user", "content": "可以使用延迟双删。"},
            {"role": "assistant", "content": "再补充一下热点 key 的处理方式。"},
            {"role": "user", "content": "可以做本地缓存和限流。"},
            {"role": "assistant", "content": "我还想追问一下故障恢复方案。"},
        ]

        result = calculate_interview_progress(history, self.plan)

        self.assertEqual(result["current_q_idx"], 1)
        self.assertGreaterEqual(result["follow_up_count"], 3)
        self.assertFalse(result["is_complete"])

    def test_last_question_initial_prompt_is_not_complete(self):
        """刚进入最后一题时，不能仅因索引到末尾就标记完成。"""
        history = [
            {"role": "assistant", "content": "第一个问题，请介绍一个你最近负责的项目。"},
            {"role": "user", "content": "我做过一个订单系统。"},
            {"role": "assistant", "content": "第二个问题，请说明你会如何设计一个高并发缓存系统。"},
        ]

        result = calculate_interview_progress(history, self.plan)

        self.assertEqual(result["current_q_idx"], 1)
        self.assertEqual(result["follow_up_count"], 0)
        self.assertFalse(result["is_complete"])

    def test_last_question_completes_with_explicit_closing(self):
        """最后一题后出现明确结束语时，才标记完成。"""
        history = [
            {"role": "assistant", "content": "第一个问题，请介绍一个你最近负责的项目。"},
            {"role": "user", "content": "我做过一个订单系统。"},
            {"role": "assistant", "content": "第二个问题，请说明你会如何设计一个高并发缓存系统。"},
            {"role": "user", "content": "我会说明架构、缓存和降级。"},
            {"role": "assistant", "content": "今天的面试就到这里，面试结束，辛苦了。"},
        ]

        result = calculate_interview_progress(history, self.plan)

        self.assertTrue(result["is_complete"])

    def test_closing_keywords_on_non_last_question_do_not_complete(self):
        """非末题即使出现结束相关表述，也不能直接标记整场面试完成。"""
        history = [
            {"role": "assistant", "content": "第一个问题，请介绍一个你最近负责的项目。"},
            {"role": "user", "content": "我做过一个订单系统。"},
            {"role": "assistant", "content": "这部分先到这里，后面还有问题，我们继续。"},
        ]

        result = calculate_interview_progress(history, self.plan)

        self.assertEqual(result["current_q_idx"], 0)
        self.assertFalse(result["is_complete"])

    def test_short_acknowledgement_is_not_counted_as_follow_up(self):
        """短确认语不应被当成追问轮次。"""
        history = [
            {"role": "assistant", "content": "第一个问题，请介绍一个你最近负责的项目。"},
            {"role": "user", "content": "我做过一个订单系统。"},
            {"role": "assistant", "content": "好的"},
        ]

        result = calculate_interview_progress(history, self.plan)

        self.assertEqual(result["current_q_idx"], 0)
        self.assertEqual(result["follow_up_count"], 0)
        self.assertFalse(result["is_complete"])

    def test_moving_to_next_question_resets_follow_up_count(self):
        """从追问切到下一题后，追问计数应重置。"""
        history = [
            {"role": "assistant", "content": "第一个问题，请介绍一个你最近负责的项目。"},
            {"role": "user", "content": "我做过一个订单系统。"},
            {"role": "assistant", "content": "能补充一下你在项目里的职责吗？"},
            {"role": "user", "content": "我负责后端核心接口。"},
            {"role": "assistant", "content": "第二个问题，请说明你会如何设计一个高并发缓存系统。"},
        ]

        result = calculate_interview_progress(history, self.plan)

        self.assertEqual(result["current_q_idx"], 1)
        self.assertEqual(result["follow_up_count"], 0)
        self.assertFalse(result["is_complete"])

    def test_empty_plan_never_completes(self):
        """没有面试计划时不能产生完成态。"""
        result = calculate_interview_progress(
            [{"role": "assistant", "content": "今天的面试就到这里，面试结束。"}],
            [],
        )

        self.assertFalse(result["is_complete"])


class VoiceInterviewClosingMessageTest(unittest.TestCase):
    def test_explicit_closing_variants_are_recognized(self):
        """常见明确结束语应被识别。"""
        closing_messages = [
            "面试结束，辛苦了。",
            "今天的面试就到这里。",
            "本轮面试就到这里，感谢你的参加。",
            "谢谢你的参加，再见。",
        ]

        for message in closing_messages:
            with self.subTest(message=message):
                self.assertTrue(is_interview_closing_message(message))

    def test_non_closing_messages_are_ignored(self):
        """未明确结束整场面试的表述不能触发完成态。"""
        non_closing_messages = [
            "",
            "这道题先到这里，我们进入下一题。",
            "不要结束面试，我们继续看缓存一致性。",
            "还没到面试结束，我们再补充一个点。",
        ]

        for message in non_closing_messages:
            with self.subTest(message=message):
                self.assertFalse(is_interview_closing_message(message))


class TextInterviewRouteTest(unittest.TestCase):
    def test_index_at_end_without_summary_flag_does_not_route_to_summary(self):
        """文字面试中，索引到末尾但未显式准备总结时不能结束。"""
        state = {
            "current_question_index": 2,
            "interview_plan": [{"content": "一"}, {"content": "二"}],
            "ready_for_summary": False,
        }

        self.assertEqual(route_after_responder(state), END)

    def test_missing_summary_flag_does_not_route_to_summary(self):
        """旧状态缺少 ready_for_summary 时默认继续等待，而不是提前总结。"""
        state = {
            "current_question_index": 2,
            "interview_plan": [{"content": "一"}, {"content": "二"}],
        }

        self.assertEqual(route_after_responder(state), END)

    def test_ready_for_summary_routes_to_summary(self):
        """只有 responder 明确声明可以总结时，才进入总结节点。"""
        state = {
            "current_question_index": 2,
            "interview_plan": [{"content": "一"}, {"content": "二"}],
            "ready_for_summary": True,
        }

        self.assertEqual(route_after_responder(state), "summary")


if __name__ == "__main__":
    unittest.main()
