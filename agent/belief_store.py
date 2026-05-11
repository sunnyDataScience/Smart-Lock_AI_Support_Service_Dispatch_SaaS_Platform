"""BeliefState 持久化 — belief_states 表的最小 CRUD。

每輪 Turn Cycle 結束後：
1. save_belief(pool, thread_id, user_id, belief) — 寫一筆新 row
2. load_latest_belief(pool, thread_id) — 載入上一輪 belief 作為下輪輸入

不做 upsert：每輪一筆 immutable，方便 replay UI timeline + audit。
"""

from __future__ import annotations

import json

from psycopg_pool import AsyncConnectionPool

from belief import BeliefState


async def save_belief(
    pool: AsyncConnectionPool,
    *,
    thread_id: str,
    user_id: str,
    belief: BeliefState,
) -> None:
    """寫一筆 belief_states row。"""
    payload = json.loads(belief.to_json())
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO belief_states (belief_id, user_id, thread_id, turn_id, payload)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (belief_id) DO NOTHING
            """,
            (
                belief.belief_id,
                user_id,
                thread_id,
                belief.turn_id,
                json.dumps(payload, ensure_ascii=False),
            ),
        )


async def load_latest_belief(
    pool: AsyncConnectionPool,
    *,
    thread_id: str,
) -> BeliefState | None:
    """載入此 thread 最新一輪 belief（turn_id 最大）。沒有則回 None。"""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT payload FROM belief_states
                WHERE thread_id = %s
                ORDER BY turn_id DESC, created_at DESC
                LIMIT 1
                """,
                (thread_id,),
            )
            row = await cur.fetchone()
    if row is None:
        return None
    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return BeliefState.from_dict(payload)


async def load_thread_timeline(
    pool: AsyncConnectionPool,
    *,
    thread_id: str,
    limit: int = 50,
) -> list[BeliefState]:
    """載入整條 thread 的 belief timeline（turn_id 升冪），供 replay UI。"""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT payload FROM belief_states
                WHERE thread_id = %s
                ORDER BY turn_id ASC
                LIMIT %s
                """,
                (thread_id, limit),
            )
            rows = await cur.fetchall()
    out: list[BeliefState] = []
    for (raw,) in rows:
        payload = raw if isinstance(raw, dict) else json.loads(raw)
        out.append(BeliefState.from_dict(payload))
    return out
