"""pgvector 存取層 — upsert 與 cosine 檢索。

治理（ADR-010）：
  - 每條查詢 WHERE 必帶 tenant_id（default deny：無 tenant 直接拒絕）
  - manual 檢索帶品牌/型號 gating（brand/model 相符或 'general' 通用列）
  - case 檢索閾值 similarity ≥ 0.85、排除 is_active=false / deleted_at 非空
"""

import json
import os
import uuid

import psycopg

CASE_SIMILARITY_THRESHOLD = 0.85
DEFAULT_TOP_K = 5


def _conninfo() -> str:
    uri = os.getenv("RAG_POSTGRES_URI") or os.getenv("POSTGRES_URI")
    if not uri:
        raise RuntimeError("需要 RAG_POSTGRES_URI 或 POSTGRES_URI")
    return uri


def tenant_id() -> str:
    """default deny：tenant 未設定即拒絕服務，不退回任何『全庫』查詢。"""
    tid = os.getenv("RAG_TENANT_ID")
    if not tid:
        raise RuntimeError("需要 RAG_TENANT_ID（ADR-010：查詢必帶 tenant，default deny）")
    return str(uuid.UUID(tid))  # 驗格式


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.7g}" for v in vec) + "]"


def upsert_manual_chunks(rows: list[dict], *, embed_model: str) -> int:
    """冪等 upsert（ON CONFLICT (tenant_id, chunk_id)）。rows 需含 embedding。"""
    tid = tenant_id()
    written = 0
    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO rag_manual_chunks
                    (tenant_id, chunk_id, brand, model, category, content,
                     embedding, embedding_model, source_type, source, provenance)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s::jsonb)
                ON CONFLICT (tenant_id, chunk_id) DO UPDATE SET
                    brand = EXCLUDED.brand,
                    model = EXCLUDED.model,
                    category = EXCLUDED.category,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    source_type = EXCLUDED.source_type,
                    source = EXCLUDED.source,
                    provenance = EXCLUDED.provenance,
                    is_active = TRUE,
                    updated_at = now()
                """,
                (
                    tid, r["id"], r.get("brand", "general"),
                    r.get("model", "general"), r.get("category"), r["text"],
                    _vec_literal(r["embedding"]), embed_model,
                    r.get("source_type"), r.get("source"),
                    json.dumps(r.get("provenance", {}), ensure_ascii=False),
                ),
            )
            written += 1
        conn.commit()
    return written


def search_manual(query_vec: list[float], *, brand: str, model: str,
                  top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """手冊語料 cosine 檢索；brand/model gating（含 'general' 通用列）。"""
    tid = tenant_id()
    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, brand, model, category, content, source_type, source,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM rag_manual_chunks
            WHERE tenant_id = %s
              AND is_active
              AND (brand = %s OR brand = 'general')
              AND (model = %s OR model = 'general')
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (_vec_literal(query_vec), tid, brand, model,
             _vec_literal(query_vec), top_k),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def search_cases(query_vec: list[float], *, brand: str | None = None,
                 model: str | None = None, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """案例史 cosine 檢索；similarity ≥ 0.85（ADR-010），brand/model 可選過濾。

    表為 kb-v2 形狀（Schema.sql）＋095 併形欄（CR-0140）：欄名 problem_description /
    solution，以別名輸出 symptom / resolution 維持 MCP 工具契約不變。
    embedding IS NOT NULL：api 端寫入的案例（sop adopt / 手動）不帶向量，
    只有 refinery Publisher 灌入的列可被語義檢索。
    """
    tid = tenant_id()
    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text AS id, brand, model,
                   problem_description AS symptom, solution AS resolution,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM case_entries
            WHERE tenant_id = %s
              AND embedding IS NOT NULL
              AND is_active
              AND deleted_at IS NULL
              AND (%s::varchar IS NULL OR brand = %s OR brand = 'general')
              AND (%s::varchar IS NULL OR model = %s OR model = 'general')
              AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (_vec_literal(query_vec), tid,
             brand, brand, model, model,
             _vec_literal(query_vec), CASE_SIMILARITY_THRESHOLD,
             _vec_literal(query_vec), top_k),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
