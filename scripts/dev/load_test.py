"""輕量壓測(20260715 清單 #26,上線前必做)。

設計:
- 單次登入拿 token 重用——**不壓登入端點**(A1 防爆破會鎖帳號)。
- 只壓讀端點(不產生資料、可重複跑)。
- 統計:成功率 / RPS / p50 / p95 / p99(ms)。
- 本機 docker 數字=基線參考;雲端 Cloud Run 另測(env BASE_* 可覆寫)。

用法:
  uv run python scripts/dev/load_test.py                 # 預設 20 併發 × 300 req/端點
  CONCURRENCY=50 REQUESTS=500 uv run python scripts/dev/load_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
import urllib.request

import aiohttp

BRAND = os.getenv("BASE_BRAND", "http://localhost:8001")
TECH = os.getenv("BASE_TECH", "http://localhost:8002")
TENANT = os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000001")
CONCURRENCY = int(os.getenv("CONCURRENCY", "20"))
REQUESTS = int(os.getenv("REQUESTS", "300"))


def login(base: str, path: str, body: dict) -> str:
    req = urllib.request.Request(
        f"{base}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["data"]["access_token"]


async def hit(session: aiohttp.ClientSession, url: str, headers: dict,
              latencies: list, errors: list) -> None:
    t0 = time.perf_counter()
    try:
        async with session.get(url, headers=headers) as r:
            await r.read()
            if r.status >= 400:
                errors.append(r.status)
            else:
                latencies.append((time.perf_counter() - t0) * 1000)
    except Exception as exc:  # noqa: BLE001
        errors.append(str(type(exc).__name__))


async def bench(name: str, url: str, headers: dict) -> dict:
    latencies: list[float] = []
    errors: list = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async def bound(session):
        async with sem:
            await hit(session, url, headers, latencies, errors)

    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    t0 = time.perf_counter()
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        await asyncio.gather(*(bound(session) for _ in range(REQUESTS)))
    wall = time.perf_counter() - t0

    ok = len(latencies)
    result = {
        "endpoint": name,
        "requests": REQUESTS,
        "ok": ok,
        "errors": len(errors),
        "error_sample": list({str(e) for e in errors})[:3],
        "rps": round(ok / wall, 1) if wall else 0,
        "p50_ms": round(statistics.median(latencies), 1) if latencies else None,
        "p95_ms": round(statistics.quantiles(latencies, n=20)[18], 1) if ok >= 20 else None,
        "p99_ms": round(statistics.quantiles(latencies, n=100)[98], 1) if ok >= 100 else None,
        "max_ms": round(max(latencies), 1) if latencies else None,
    }
    print(f"  {name:44s} ok={ok}/{REQUESTS} rps={result['rps']:>7} "
          f"p50={result['p50_ms']} p95={result['p95_ms']} p99={result['p99_ms']}")
    return result


async def main() -> None:
    print(f"壓測開始:併發={CONCURRENCY} 每端點={REQUESTS} req")
    admin_token = login(BRAND, "/api/v1/auth/login",
                        {"email": "test@lock-ai.com", "password": "changeme123"})
    tech_token = login(TECH, "/api/v1/technicians/login",
                       {"identifier": "test@lock-ai.com", "password": "changeme123"})
    h_admin = {"Authorization": f"Bearer {admin_token}", "X-Tenant-ID": TENANT}
    h_tech = {"Authorization": f"Bearer {tech_token}", "X-Tenant-ID": TENANT}

    targets = [
        ("brand /health(無認證基線)", f"{BRAND}/health", {}),
        ("brand GET /api/v1/work-orders?limit=20", f"{BRAND}/api/v1/work-orders?limit=20", h_admin),
        ("brand GET /tenants/{t}/quotes", f"{BRAND}/tenants/{TENANT}/quotes", h_admin),
        ("brand GET /api/v1/problem-cards?limit=20", f"{BRAND}/api/v1/problem-cards?limit=20", h_admin),
        ("brand GET /tenants/{t}/notifications", f"{BRAND}/tenants/{TENANT}/notifications?limit=20", h_admin),
        ("tech  GET /api/v1/work-orders?limit=20", f"{TECH}/api/v1/work-orders?limit=20", h_tech),
        ("tech  GET me/line-binding", f"{TECH}/api/v1/technicians/me/line-binding", h_tech),
    ]
    results = []
    for name, url, headers in targets:
        results.append(await bench(name, url, headers))

    out = {"concurrency": CONCURRENCY, "requests_per_endpoint": REQUESTS,
           "results": results}
    path = os.getenv("REPORT_JSON", "/tmp/load_test_result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n完成,JSON → {path}")


if __name__ == "__main__":
    asyncio.run(main())
