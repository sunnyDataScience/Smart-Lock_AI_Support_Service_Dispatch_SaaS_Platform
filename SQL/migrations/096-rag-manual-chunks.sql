-- ═══════════════════════════════════════════════════════════════════════════
-- 096-rag-manual-chunks.sql — RAG 事實語料表改名自持(WBS 2.2.2 收尾/CR-0142)
--
-- 撞名事故(與 CR-0140 case_entries 同型,2026-07-10 查實):
--   Schema.sql:328 的 manual_chunks = kb-v2 形狀(manuals FK 子表,PDF 章節塊,
--   manual_id/source_pdf/page_number);Schema_rag.sql 曾以同名 CREATE IF NOT
--   EXISTS 定義 RAG 語料形狀 → 對所有正規 bootstrap 的庫恆 no-op ——
--   **RAG 語義層主表從未真正存在**,search_manual 對實庫 SQL ERROR 被
--   MCP fail-soft 遮蔽(agent 恆得 RAG_UNAVAILABLE)。
--
-- 解法(異於 case_entries 併形):kb manual_chunks 與 RAG 語料語意不同
--   (per-manual PDF 塊 vs tenant 語料+provenance),不可併形 → RAG 表改名
--   `rag_manual_chunks` 自持,kb 表不動。rag/store.py 同步改名(CR-0142)。
-- 落庫:品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_manual_chunks (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    chunk_id        VARCHAR(32) NOT NULL,          -- knowledge-pipeline 冪等 id(sha256[:16])
    brand           VARCHAR(100) NOT NULL,          -- 'general' = 跨品牌通用
    model           VARCHAR(100) NOT NULL DEFAULT 'general',
    category        VARCHAR(50),
    content         TEXT NOT NULL,
    embedding       vector(768) NOT NULL,           -- RAG_EMBED_MODEL(預設 multilingual-002)
    embedding_model VARCHAR(100) NOT NULL,
    source_type     VARCHAR(50),                    -- youtube / video / website / references
    source          TEXT,
    provenance      JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_rag_manual_chunks_hnsw
    ON rag_manual_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_rag_manual_chunks_scope
    ON rag_manual_chunks (tenant_id, brand, model) WHERE is_active;

COMMENT ON TABLE rag_manual_chunks IS 'RAG 事實語料(bronze-only;灌注自 facts.jsonl 與 lockcore references);原名 manual_chunks 與 kb-v2 表撞名,096 改名自持(CR-0142)';
