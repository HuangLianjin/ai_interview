"""Agent 运行告警检查。

用法：
  python backend/scripts/check_alerts.py --days 1
  PUSHPLUS_TOKEN=xxx python backend/scripts/check_alerts.py
  ALERT_WEBHOOK_URL=https://... python backend/scripts/check_alerts.py

建议用 cron 每 10 分钟执行一次，触发阈值时推送告警。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass


def build_alerts(summary: dict, metrics: dict, args) -> list[str]:
    alerts: list[str] = []
    if summary["total_runs"] >= args.min_runs and summary["success_rate"] < args.min_success_rate:
        alerts.append(
            f"面试运行成功率过低：{summary['success_rate']:.1%}（阈值 {args.min_success_rate:.1%}）"
        )
    if summary["total_runs"] >= args.min_runs and summary["p95_latency_ms"] > args.max_p95_ms:
        alerts.append(
            f"P95 延迟过高：{summary['p95_latency_ms']:.0f}ms（阈值 {args.max_p95_ms}ms）"
        )
    if metrics["open_eval_failures"] > args.max_open_failures:
        alerts.append(
            f"待修复评测失败样本过多：{metrics['open_eval_failures']} 条（阈值 {args.max_open_failures}）"
        )
    if metrics["feedback_total"] >= args.min_feedback and metrics["feedback_avg_rating"] < args.min_avg_rating:
        alerts.append(
            f"用户平均评分偏低：{metrics['feedback_avg_rating']}（阈值 {args.min_avg_rating}）"
        )
    if metrics["feedback_low_rating"] >= args.max_low_ratings:
        alerts.append(
            f"低分反馈较多：{metrics['feedback_low_rating']} 条（阈值 {args.max_low_ratings}）"
        )
    return alerts


def send_alert(text: str) -> None:
    pushplus_token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()

    if pushplus_token:
        payload = json.dumps(
            {"token": pushplus_token, "title": "职面 AI 运行告警", "content": text}
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://www.pushplus.plus/send",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("PushPlus 已发送:", resp.status)

    if webhook_url:
        payload = json.dumps({"msgtype": "text", "text": {"content": text}}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("Webhook 已发送:", resp.status)

    if not pushplus_token and not webhook_url:
        print("[info] 未配置 PUSHPLUS_TOKEN 或 ALERT_WEBHOOK_URL，仅打印告警")


async def run(args) -> int:
    from app.services.trace_service import get_product_metrics, get_trace_summary

    summary = await get_trace_summary(days=args.days)
    metrics = await get_product_metrics(days=args.days)
    alerts = build_alerts(summary, metrics, args)

    print("运行摘要:", json.dumps(summary, ensure_ascii=False))
    print("产品指标:", json.dumps(metrics, ensure_ascii=False))

    if not alerts:
        print("检查通过，无告警")
        return 0

    text = "【职面 AI 运行告警】\n" + "\n".join(f"- {a}" for a in alerts)
    print(text)
    if not args.dry_run:
        send_alert(text)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 运行告警检查")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--min-runs", type=int, default=3)
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    parser.add_argument("--max-p95-ms", type=float, default=8000)
    parser.add_argument("--max-open-failures", type=int, default=20)
    parser.add_argument("--min-feedback", type=int, default=5)
    parser.add_argument("--min-avg-rating", type=float, default=3.5)
    parser.add_argument("--max-low-ratings", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
