"""建立 product_docs + product_docs_history 兩張表。

可重跑（CREATE TABLE IF NOT EXISTS），idempotent。

跑法：
    cd agent && uv run python scripts/setup_product_docs_schema.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 讓 agent 內的 import 可解
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

# 讀專案根目錄 .env（與 agent v1 共用同一份）
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")


CREATE_PRODUCT_DOCS = """
CREATE TABLE IF NOT EXISTS product_docs (
    name           VARCHAR(200) PRIMARY KEY,
    brand          VARCHAR(50)  NOT NULL,
    model          VARCHAR(100),
    description    TEXT NOT NULL,
    body           TEXT NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by     VARCHAR(100) NOT NULL DEFAULT 'system'
)
"""

CREATE_PRODUCT_DOCS_BRAND_IDX = """
CREATE INDEX IF NOT EXISTS product_docs_brand_idx ON product_docs(brand)
"""

CREATE_PRODUCT_DOCS_HISTORY = """
CREATE TABLE IF NOT EXISTS product_docs_history (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    body            TEXT NOT NULL,
    description     TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    updated_by      VARCHAR(100) NOT NULL,
    change_reason   TEXT
)
"""

CREATE_HISTORY_NAME_TS_IDX = """
CREATE INDEX IF NOT EXISTS product_docs_history_name_ts_idx
ON product_docs_history(name, updated_at DESC)
"""


async def main() -> None:
    import psycopg

    uri = os.getenv("POSTGRES_URI")
    if not uri:
        print("ERROR: POSTGRES_URI 未設定（請檢查專案根目錄 .env）")
        sys.exit(1)

    print("=" * 60)
    print("product_docs schema setup")
    print(f"DB: {uri}")
    print("=" * 60)
    print()

    async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as conn:
        for stmt, name in [
            (CREATE_PRODUCT_DOCS, "product_docs"),
            (CREATE_PRODUCT_DOCS_BRAND_IDX, "product_docs_brand_idx"),
            (CREATE_PRODUCT_DOCS_HISTORY, "product_docs_history"),
            (CREATE_HISTORY_NAME_TS_IDX, "product_docs_history_name_ts_idx"),
        ]:
            await conn.execute(stmt)
            print(f"    ✓ {name}")

    print()
    print("=" * 60)
    print("✓ Schema 已就緒。下一步：python scripts/seed_product_docs_from_agent.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
