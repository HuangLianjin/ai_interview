"""轻量并发压测脚本：验证多用户并发下的 QPS、P95 和错误率。

用法示例：
  python backend/scripts/load_test.py --url https://interview.huanglianjin.icu/health --requests 100 --concurrency 10
  python backend/scripts/load_test.py --url http://127.0.0.1:8000/health --requests 200 --concurrency 20 --output load_report.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx


async def one_request(client: httpx.AsyncClient, method: str, url: str, json_body: dict | None, headers: dict):
    started = time.perf_counter()
    try:
        response = await client.request(method, url, json=json_body, headers=headers)
        return {
            "ok": response.status_code < 500,
            "status": response.status_code,
            "latency_ms": (time.perf_counter() - started) * 1000,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "error": str(e),
        }


async def run(args) -> dict:
    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    if args.header:
        for item in args.header:
            key, _, value = item.partition(":")
            headers[key.strip()] = value.strip()

    json_body = json.loads(args.json) if args.json else None
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    timeout = httpx.Timeout(args.timeout)

    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(limits=limits, timeout=timeout, verify=not args.insecure) as client:
        async def bounded():
            async with semaphore:
                return await one_request(client, args.method, args.url, json_body, headers)

        started = time.perf_counter()
        results = await asyncio.gather(*(bounded() for _ in range(args.requests)))
        total_seconds = time.perf_counter() - started

    latencies = sorted(r["latency_ms"] for r in results)
    success = sum(1 for r in results if r["ok"])
    p95_index = max(0, int(len(latencies) * 0.95) - 1)
    report = {
        "url": args.url,
        "method": args.method,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "success": success,
        "failed": args.requests - success,
        "success_rate": round(success / args.requests, 4),
        "total_seconds": round(total_seconds, 3),
        "qps": round(args.requests / total_seconds, 2) if total_seconds else 0,
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0,
        "p50_latency_ms": round(latencies[len(latencies) // 2], 1) if latencies else 0,
        "p95_latency_ms": round(latencies[p95_index], 1) if latencies else 0,
        "max_latency_ms": round(max(latencies), 1) if latencies else 0,
        "status_counts": {},
    }
    for r in results:
        key = str(r["status"])
        report["status_counts"][key] = report["status_counts"].get(key, 0) + 1
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="轻量并发压测")
    parser.add_argument("--url", required=True)
    parser.add_argument("--method", default="GET")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--json", help="POST 的 JSON 字符串")
    parser.add_argument("--token", help="Bearer Token")
    parser.add_argument("--header", action="append", help="额外请求头，格式 Key:Value")
    parser.add_argument("--insecure", action="store_true", help="跳过 TLS 校验")
    parser.add_argument("--output", help="报告输出路径")
    args = parser.parse_args()

    report = asyncio.run(run(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("报告已写入:", args.output)


if __name__ == "__main__":
    main()
