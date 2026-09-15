"""常驻告警检查器：按固定间隔检查阈值，仅在告警内容变化时推送。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.check_alerts import build_alerts, send_alert  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="常驻 Agent 告警检查器")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--min-runs", type=int, default=3)
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    parser.add_argument("--max-p95-ms", type=float, default=8000)
    parser.add_argument("--max-open-failures", type=int, default=20)
    parser.add_argument("--min-feedback", type=int, default=5)
    parser.add_argument("--min-avg-rating", type=float, default=3.5)
    parser.add_argument("--max-low-ratings", type=int, default=3)
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.getenv("ALERT_INTERVAL_SECONDS", "600")),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def check_once(args: argparse.Namespace, last_signature: str = "") -> str:
    from app.services.trace_service import get_product_metrics, get_trace_summary

    summary = await get_trace_summary(days=args.days)
    metrics = await get_product_metrics(days=args.days)
    alerts = build_alerts(summary, metrics, args)
    signature = hashlib.sha256(
        json.dumps(alerts, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if not alerts:
        return ""
    if signature != last_signature:
        text = "【职面 AI 运行告警】\n" + "\n".join(f"- {item}" for item in alerts)
        print(text, flush=True)
        if not args.dry_run:
            send_alert(text)
    return signature


async def main() -> None:
    args = parse_args()
    last_signature = ""
    while True:
        try:
            last_signature = await check_once(args, last_signature)
        except Exception as exc:
            print(f"[alert-loop] 检查失败: {exc}", flush=True)
        await asyncio.sleep(max(30, args.interval_seconds))


if __name__ == "__main__":
    asyncio.run(main())
