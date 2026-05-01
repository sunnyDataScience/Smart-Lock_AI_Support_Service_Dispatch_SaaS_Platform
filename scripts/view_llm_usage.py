#!/usr/bin/env python3
"""查看 llm_usage_log 表（取代 Opik 角色）。

從專案根目錄執行，會自動載入根目錄 .env 的 POSTGRES_URI。

用法：
    python scripts/view_llm_usage.py                            # 近 24h 概覽 + 最近明細
    python scripts/view_llm_usage.py --since 1h                 # 近 1 小時
    python scripts/view_llm_usage.py --by-call-site             # 按 call_site 聚合成本
    python scripts/view_llm_usage.py --slow --threshold 5000    # latency >= 5s 的呼叫
    python scripts/view_llm_usage.py --user-id <uid>            # 單一用戶
    python scripts/view_llm_usage.py --by-day                   # 按日聚合（成本趨勢）
    python scripts/view_llm_usage.py --limit 50                 # 明細顯示筆數
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime

try:
    from dotenv import load_dotenv

    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_ROOT, ".env"))
except Exception:
    pass


_SINCE_RE = re.compile(r"^(\d+)([smhd])$")


def parse_since(s: str) -> str:
    """將 '24h' / '15m' / '7d' 轉成 PostgreSQL interval 字串。"""
    m = _SINCE_RE.match(s.strip())
    if not m:
        raise SystemExit(f"--since 格式錯誤: {s}（範例: 1h, 30m, 24h, 7d）")
    n, unit = m.group(1), m.group(2)
    unit_map = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    return f"{n} {unit_map[unit]}"


def fmt_int(v):
    return f"{v:,}" if isinstance(v, int) else "—"


def fmt_ts(ts) -> str:
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)[:19] if ts else "—"


async def overview(conn, since_interval: str, user_id: str | None):
    where = ["timestamp >= NOW() - %s::interval"]
    params: list = [since_interval]
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    where_sql = " AND ".join(where)

    title_user = f", user={user_id}" if user_id else ""
    print(f"\n=== 概覽（since {since_interval}{title_user}）===")

    async with conn.cursor() as cur:
        await cur.execute(
            f"""SELECT COUNT(*),
                       SUM(input_tokens), SUM(output_tokens), SUM(total_tokens),
                       AVG(latency_ms)::int, MAX(latency_ms),
                       SUM(CASE WHEN success THEN 0 ELSE 1 END)
                FROM llm_usage_log WHERE {where_sql}""",
            params,
        )
        row = await cur.fetchone()
    if not row or row[0] == 0:
        print("  (無資料)")
        return
    cnt, ti, to, tt, avg_lat, max_lat, fails = row
    print(f"  呼叫數:     {fmt_int(cnt)}（失敗 {fmt_int(fails)} 筆）")
    print(f"  Tokens:     in={fmt_int(ti)}  out={fmt_int(to)}  total={fmt_int(tt)}")
    print(f"  Latency:    avg={fmt_int(avg_lat)}ms  max={fmt_int(max_lat)}ms")


async def by_call_site(conn, since_interval: str, user_id: str | None):
    where = ["timestamp >= NOW() - %s::interval"]
    params: list = [since_interval]
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    where_sql = " AND ".join(where)

    print(f"\n=== 按 call_site 聚合（since {since_interval}）===")
    print(f"  {'call_site':<22} {'count':>8} {'tokens':>12} {'avg_lat':>10} {'errors':>8}")
    print(f"  {'-' * 22} {'-' * 8} {'-' * 12} {'-' * 10} {'-' * 8}")

    async with conn.cursor() as cur:
        await cur.execute(
            f"""SELECT call_site, COUNT(*), SUM(total_tokens), AVG(latency_ms)::int,
                       SUM(CASE WHEN success THEN 0 ELSE 1 END)
                FROM llm_usage_log WHERE {where_sql}
                GROUP BY call_site ORDER BY COUNT(*) DESC""",
            params,
        )
        rows = await cur.fetchall()
    if not rows:
        print("  (無資料)")
        return
    for site, cnt, tt, avg_lat, fails in rows:
        print(
            f"  {site:<22} {fmt_int(cnt):>8} {fmt_int(tt):>12} "
            f"{fmt_int(avg_lat) + 'ms':>10} {fmt_int(fails):>8}"
        )


async def by_day(conn, since_interval: str, user_id: str | None):
    where = ["timestamp >= NOW() - %s::interval"]
    params: list = [since_interval]
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    where_sql = " AND ".join(where)

    print(f"\n=== 按日聚合（since {since_interval}）===")
    print(f"  {'date':<12} {'count':>8} {'tokens':>12} {'avg_lat':>10} {'errors':>8}")
    print(f"  {'-' * 12} {'-' * 8} {'-' * 12} {'-' * 10} {'-' * 8}")

    async with conn.cursor() as cur:
        await cur.execute(
            f"""SELECT DATE(timestamp AT TIME ZONE 'Asia/Taipei') AS d,
                       COUNT(*), SUM(total_tokens), AVG(latency_ms)::int,
                       SUM(CASE WHEN success THEN 0 ELSE 1 END)
                FROM llm_usage_log WHERE {where_sql}
                GROUP BY d ORDER BY d DESC""",
            params,
        )
        rows = await cur.fetchall()
    if not rows:
        print("  (無資料)")
        return
    for d, cnt, tt, avg_lat, fails in rows:
        print(
            f"  {str(d):<12} {fmt_int(cnt):>8} {fmt_int(tt):>12} "
            f"{fmt_int(avg_lat) + 'ms':>10} {fmt_int(fails):>8}"
        )


async def slow_calls(conn, since_interval: str, threshold_ms: int, limit: int):
    print(f"\n=== 慢呼叫（latency >= {threshold_ms}ms, since {since_interval}, top {limit}）===")
    async with conn.cursor() as cur:
        await cur.execute(
            """SELECT timestamp, user_id, call_site, model, latency_ms, total_tokens, error_type
               FROM llm_usage_log
               WHERE timestamp >= NOW() - %s::interval AND latency_ms >= %s
               ORDER BY latency_ms DESC LIMIT %s""",
            (since_interval, threshold_ms, limit),
        )
        rows = await cur.fetchall()
    if not rows:
        print("  (無資料)")
        return
    for ts, uid, site, model, lat, tt, err in rows:
        flag = f" [error={err}]" if err else ""
        print(
            f"  {fmt_ts(ts)} | {site:<22} | {fmt_int(lat) + 'ms':>9} | "
            f"tok={fmt_int(tt):>9} | {(uid or '')[:24]}{flag}"
        )


async def recent_detail(conn, since_interval: str, user_id: str | None, limit: int):
    where = ["timestamp >= NOW() - %s::interval"]
    params: list = [since_interval]
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    where_sql = " AND ".join(where)

    print(f"\n=== 明細（最近 {limit} 筆）===")
    async with conn.cursor() as cur:
        await cur.execute(
            f"""SELECT timestamp, user_id, call_site, model,
                       input_tokens, output_tokens, total_tokens, latency_ms,
                       success, error_type
                FROM llm_usage_log WHERE {where_sql}
                ORDER BY timestamp DESC LIMIT %s""",
            (*params, limit),
        )
        rows = await cur.fetchall()
    if not rows:
        print("  (無資料)")
        return
    for ts, uid, site, model, ti, to, tt, lat, ok, err in rows:
        status = "OK" if ok else f"FAIL({err})"
        print(
            f"  {fmt_ts(ts)} | {site:<22} | in={fmt_int(ti):>6} out={fmt_int(to):>6} "
            f"tot={fmt_int(tt):>6} lat={fmt_int(lat) + 'ms':>8} | {status:<14} | {(uid or '')[:24]}"
        )


async def main():
    parser = argparse.ArgumentParser(description="LLM 用量與延遲查詢 (llm_usage_log)")
    parser.add_argument("--since", default="24h", help="時間範圍 (1h / 30m / 7d)")
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--by-call-site", action="store_true", help="按 call_site 聚合")
    parser.add_argument("--by-day", action="store_true", help="按日聚合（趨勢）")
    parser.add_argument("--slow", action="store_true", help="顯示慢呼叫")
    parser.add_argument("--threshold", type=int, default=5000, help="慢呼叫門檻 ms（預設 5000）")
    parser.add_argument("--limit", type=int, default=30, help="明細 / slow 顯示筆數")
    args = parser.parse_args()

    pg_uri = os.getenv("POSTGRES_URI")
    if not pg_uri:
        print("[錯誤] 環境變數 POSTGRES_URI 未設定。請確認專案根目錄 .env。")
        sys.exit(1)

    since_interval = parse_since(args.since)

    try:
        from psycopg import AsyncConnection
    except ImportError:
        print("[錯誤] 缺少 psycopg。請執行：pip install -r agent/requirements.txt")
        sys.exit(1)

    conn = await AsyncConnection.connect(pg_uri)
    try:
        # 確保表存在（與 agent/storage/postgres_impl.py DDL 一致）
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id BIGSERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_id TEXT NOT NULL,
                turn_id TEXT,
                call_site VARCHAR(50) NOT NULL,
                model VARCHAR(100) NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                latency_ms INTEGER,
                success BOOLEAN NOT NULL DEFAULT TRUE,
                error_type VARCHAR(50),
                metadata JSONB
            )
        """)
        await conn.commit()

        await overview(conn, since_interval, args.user_id)

        if args.by_call_site:
            await by_call_site(conn, since_interval, args.user_id)
        elif args.by_day:
            await by_day(conn, since_interval, args.user_id)
        elif args.slow:
            await slow_calls(conn, since_interval, args.threshold, args.limit)
        else:
            await recent_detail(conn, since_interval, args.user_id, args.limit)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
