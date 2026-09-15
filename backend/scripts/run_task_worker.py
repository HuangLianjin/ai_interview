"""后台任务 worker：消费 background_tasks 队列。

用法：
  python backend/scripts/run_task_worker.py          # 常驻
  python backend/scripts/run_task_worker.py --once   # 只处理当前一个任务
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("task-worker")


async def dispatch(task: dict) -> None:
    task_type = task["task_type"]
    payload = task.get("payload") or {}
    session_id = payload.get("session_id")

    if task_type == "profile_analysis":
        from app.core.interview_analysis import trigger_background_analysis
        await trigger_background_analysis(session_id, payload.get("api_config"))
    elif task_type == "report_generation":
        from app.services.report_service import generate_session_report
        await generate_session_report(session_id)
    else:
        raise ValueError(f"未知任务类型: {task_type}")


async def run_once() -> bool:
    from app.services.task_queue import claim_task, complete_task, fail_task

    task = await claim_task()
    if not task:
        return False
    logger.info("处理任务 id=%s type=%s", task["id"], task["task_type"])
    try:
        await dispatch(task)
        await complete_task(task["id"])
        logger.info("任务完成 id=%s", task["id"])
    except Exception as e:
        logger.exception("任务失败 id=%s", task["id"])
        await fail_task(task["id"], str(e))
    return True


async def main() -> None:
    parser = argparse.ArgumentParser(description="背景任务 worker")
    parser.add_argument("--once", action="store_true", help="只处理一个任务")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    if args.once:
        handled = await run_once()
        print("处理了一个任务" if handled else "当前没有待处理任务")
        return

    logger.info("任务 worker 启动")
    while True:
        handled = await run_once()
        if not handled:
            await asyncio.sleep(args.poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
