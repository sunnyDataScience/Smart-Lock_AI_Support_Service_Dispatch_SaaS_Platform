"""建立 belief_states 表。

可重跑（CREATE TABLE IF NOT EXISTS），idempotent。

每輪 Turn Cycle 把 BeliefState 序列化進來，供：
- 後台 replay UI 看任一輪 belief 狀態（新需求 §10）
- Calibrate audit（驗證 belief 修正歷史）
- Hypothesis Quality 人工標 baseline

跑法：
    cd agent && uv run python scripts/setup_belief_schema.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")


CREATE_BELIEF_STATES = """
CREATE TABLE IF NOT EXISTS belief_states (
    belief_id      VARCHAR(64) PRIMARY KEY,
    user_id        VARCHAR(100) NOT NULL,
    thread_id      VARCHAR(100) NOT NULL,
    turn_id        INTEGER NOT NULL,
    payload        JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

CREATE_BELIEF_STATES_THREAD_TURN_IDX = """
CREATE INDEX IF NOT EXISTS belief_states_thread_turn_idx
ON belief_states(thread_id, turn_id)
"""

CREATE_BELIEF_STATES_USER_IDX = """
CREATE INDEX IF NOT EXISTS belief_states_user_idx
ON belief_states(user_id, created_at DESC)
"""


async def main() -> None:
    import psycopg

    uri = os.getenv("POSTGRES_URI")
    if not uri:
        print("ERROR: POSTGRES_URI 未設定（請檢查專案根目錄 .env）")
        sys.exit(1)

    print("=" * 60)
    print("belief_states schema setup")
    print(f"DB: {uri}")
    print("=" * 60)
    print()

    async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as conn:
        for stmt, name in [
            (CREATE_BELIEF_STATES, "belief_states"),
            (CREATE_BELIEF_STATES_THREAD_TURN_IDX, "belief_states_thread_turn_idx"),
            (CREATE_BELIEF_STATES_USER_IDX, "belief_states_user_idx"),
        ]:
            await conn.execute(stmt)
            print(f"    ✓ {name}")

    print()
    print("=" * 60)
    print("✓ Schema 已就緒。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
