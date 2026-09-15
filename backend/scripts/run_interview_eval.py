"""面试 Agent 离线评测执行器。

用法：
  python backend/scripts/run_interview_eval.py            # 只跑确定性用例（结束语判断）
  python backend/scripts/run_interview_eval.py --live     # 跑追问和评分用例（需要配置 LLM）
  python backend/scripts/run_interview_eval.py --live --save-failures

评测维度：
1. followup：追问决策是否符合预期
2. scoring：评分是否落在合理区间
3. closing：面试结束语判断是否正确（确定性逻辑，不需要模型）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass

CASES_PATH = BACKEND_DIR / "evals" / "interview_cases.json"
REPORT_DIR = BACKEND_DIR / "evals" / "reports"


def load_cases(category: str | None = None) -> list[dict]:
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    if category:
        cases = [c for c in cases if c.get("category") == category]
    return cases


def build_api_config() -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1").strip()
    smart_model = os.getenv("SMART_MODEL", "deepseek-chat").strip()
    fast_model = os.getenv("FAST_MODEL", smart_model).strip()
    return {
        "smart": {"api_key": api_key, "base_url": base_url, "model": smart_model},
        "fast": {"api_key": api_key, "base_url": base_url, "model": fast_model},
    }


async def evaluate_followup(case: dict, api_config: dict) -> dict:
    from app.services.followup_service import decide_followup

    decision = await decide_followup(
        question=case["question"],
        answer=case["answer"],
        history=[],
        followups_so_far=0,
        api_config=api_config,
        max_follow_ups=2,
    )
    actual_followup = decision.get("action") == "followup"
    passed = actual_followup == bool(case.get("expect_followup"))
    return {
        "passed": passed,
        "actual": {
            "action": decision.get("action"),
            "followup_question": decision.get("followup_question", ""),
            "acknowledgment": decision.get("acknowledgment", ""),
        },
        "reason": "" if passed else f"期望 followup={case.get('expect_followup')}，实际={actual_followup}",
    }


async def evaluate_scoring(case: dict, api_config: dict) -> dict:
    from app.core.llms import get_llm_for_request
    from app.services.scoring_service import SCORE_PROMPT, _parse_score_response

    llm = get_llm_for_request(api_config, channel="smart")
    prompt = SCORE_PROMPT.format(
        question=case["question"],
        answer=case["answer"][:4000],
    )
    response = await llm.ainvoke(prompt)
    data = _parse_score_response(response.content)
    if not data:
        return {
            "passed": False,
            "actual": {"raw": str(getattr(response, "content", ""))[:300]},
            "reason": "评分结果无法解析为 JSON",
        }
    total = float(data.get("total") or 0)
    min_total = float(case.get("min_total", 0))
    max_total = float(case.get("max_total", 10))
    passed = min_total <= total <= max_total
    return {
        "passed": passed,
        "actual": {
            "total": total,
            "dimensions": data.get("dimensions", {}),
            "comment": data.get("comment", ""),
        },
        "reason": "" if passed else f"期望分数在 [{min_total}, {max_total}]，实际={total}",
    }


def evaluate_closing(case: dict) -> dict:
    from app.core.voice_interview import is_interview_closing_message

    actual = is_interview_closing_message(case["question"])
    passed = actual == bool(case.get("expect_closing"))
    return {
        "passed": passed,
        "actual": {"closing": actual},
        "reason": "" if passed else f"期望 closing={case.get('expect_closing')}，实际={actual}",
    }


async def run_eval(cases: list[dict], live: bool, save_failures: bool) -> dict:
    from app.services.trace_service import save_eval_failure

    api_config = build_api_config() if live else None
    if live and not api_config:
        print("[warn] 未配置 OPENAI_API_KEY，追问和评分用例将标记为 skipped")

    results = []
    passed_count = 0
    for case in cases:
        category = case.get("category")
        result = {"id": case.get("id"), "category": category, "passed": False, "skipped": False}
        try:
            if category == "closing":
                outcome = evaluate_closing(case)
            elif category in ("followup", "scoring"):
                if not api_config:
                    result["skipped"] = True
                    result["reason"] = "未配置模型 Key，跳过需要 LLM 的用例"
                    results.append(result)
                    continue
                outcome = (
                    await evaluate_followup(case, api_config)
                    if category == "followup"
                    else await evaluate_scoring(case, api_config)
                )
            else:
                result["reason"] = f"未知评测类型: {category}"
                results.append(result)
                continue
        except Exception as e:
            outcome = {"passed": False, "actual": {}, "reason": f"执行异常: {e}"}

        result.update(outcome)
        result["question"] = case.get("question", "")
        result["answer"] = case.get("answer", "")
        result["expected"] = {
            "expect_followup": case.get("expect_followup"),
            "min_total": case.get("min_total"),
            "max_total": case.get("max_total"),
            "expect_closing": case.get("expect_closing"),
        }
        results.append(result)

        if outcome.get("passed"):
            passed_count += 1
        elif save_failures and api_config is not None:
            await save_eval_failure(
                case_id=str(case.get("id")),
                category=str(category),
                question=case.get("question", ""),
                answer=case.get("answer", ""),
                expected=result["expected"],
                actual=outcome.get("actual") or {},
            )

    executed = [r for r in results if not r.get("skipped")]
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "live": live,
        "total_cases": len(results),
        "executed_cases": len(executed),
        "passed_cases": passed_count,
        "failed_cases": len(executed) - passed_count,
        "pass_rate": round(passed_count / len(executed), 4) if executed else 0.0,
        "results": results,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="面试 Agent 离线评测")
    parser.add_argument("--live", action="store_true", help="调用真实 LLM 运行追问和评分评测")
    parser.add_argument("--category", help="只跑某一类：followup / scoring / closing")
    parser.add_argument("--save-failures", action="store_true", help="把失败样本写入 eval_failures 表")
    parser.add_argument("--output", help="评测报告输出路径")
    args = parser.parse_args()

    cases = load_cases(args.category)
    if not cases:
        print("没有匹配的评测用例")
        return

    report = asyncio.run(run_eval(cases, live=args.live, save_failures=args.save_failures))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = Path(args.output) if args.output else REPORT_DIR / f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"用例总数: {report['total_cases']}")
    print(f"实际执行: {report['executed_cases']}")
    print(f"通过: {report['passed_cases']}")
    print(f"失败: {report['failed_cases']}")
    print(f"通过率: {report['pass_rate']:.2%}")
    print(f"报告文件: {output}")

    failures = [r for r in report["results"] if not r.get("passed") and not r.get("skipped")]
    if failures:
        print("\n失败样本：")
        for item in failures[:10]:
            print(f"- [{item['id']}] {item.get('reason')}")


if __name__ == "__main__":
    main()
