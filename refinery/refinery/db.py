"""品牌 DB 連線與 tenant 治理（比照 rag/rag/store.py 慣例）。

- 連線：REFINERY_POSTGRES_URI 優先，退 POSTGRES_URI
- tenant default-deny：REFINERY_TENANT_ID 未設即 RuntimeError，絕不退回全庫查詢
"""

import os
import uuid

import psycopg


def conninfo() -> str:
    uri = os.getenv("REFINERY_POSTGRES_URI") or os.getenv("POSTGRES_URI")
    if not uri:
        raise RuntimeError("需要 REFINERY_POSTGRES_URI 或 POSTGRES_URI")
    return uri


def tenant_id() -> str:
    """default deny：tenant 未設定即拒絕服務（CR-0139 D1，比照 ADR-010 治理）。"""
    tid = os.getenv("REFINERY_TENANT_ID")
    if not tid:
        raise RuntimeError("需要 REFINERY_TENANT_ID（汲取必帶 tenant，default deny）")
    return str(uuid.UUID(tid))  # 驗格式


def connect() -> psycopg.Connection:
    return psycopg.connect(conninfo())
