-- ============================================================================
-- RAG 語義層 Schema（WBS 2.2.1 / ADR-010 知識分層）
-- ============================================================================
-- 版本：v1.0
-- 日期：2026-07-09
-- 說明：
--   1. manual_chunks — 逐型號手冊事實語料（唯一事實語料，ADR-010 治理鐵律）
--      灌注來源：knowledge-pipeline storage/corpus/facts.jsonl（bronze-only 紅線，
--      provenance 帶 bronze 檔 + sha256），經 rag/ingest.py 冪等 upsert。
--   2. case_entries — 案例史（症狀→解法）。Phase D（knowledge-refinery，ADR-018）
--      HITL 精煉後灌入；本階段建表備妥，search_similar_cases 先回空集。
--   3. 檢索：768 維（text-embedding-004）HNSW cosine；查詢 WHERE 必帶 tenant_id
--      （ADR-010：default deny）。
-- 依賴：pgvector extension（品牌庫 image = pgvector/pgvector:pg17，已內建）
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- [1] manual_chunks — 手冊事實語料
-- ============================================================================

CREATE TABLE IF NOT EXISTS manual_chunks (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    chunk_id        VARCHAR(32) NOT NULL,          -- knowledge-pipeline 冪等 id（sha256[:16]）
    brand           VARCHAR(100) NOT NULL,          -- 'general' = 跨品牌通用
    model           VARCHAR(100) NOT NULL DEFAULT 'general',
    category        VARCHAR(50),                    -- setup / troubleshoot / specification / knowledge / manual
    content         TEXT NOT NULL,
    embedding       vector(768) NOT NULL,           -- text-embedding-004（ADR-010）
    embedding_model VARCHAR(100) NOT NULL,          -- 記錄產生 embedding 的模型（重嵌可辨識）
    source_type     VARCHAR(50),                    -- youtube / video / website
    source          TEXT,
    provenance      JSONB NOT NULL DEFAULT '{}',    -- bronze_path / bronze_sha256 / emitted_at
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, chunk_id)
);

-- 語義檢索主索引（cosine）
CREATE INDEX IF NOT EXISTS idx_manual_chunks_hnsw
    ON manual_chunks USING hnsw (embedding vector_cosine_ops);
-- 結構過濾（tenant + 品牌/型號 gating）
CREATE INDEX IF NOT EXISTS idx_manual_chunks_scope
    ON manual_chunks (tenant_id, brand, model) WHERE is_active;

COMMENT ON TABLE manual_chunks IS 'RAG 事實語料（ADR-010 唯一事實語料）；灌注自 knowledge-pipeline facts.jsonl，bronze-only';
COMMENT ON COLUMN manual_chunks.chunk_id IS 'knowledge-pipeline 冪等 chunk id；(tenant_id, chunk_id) 唯一，重灌 upsert';
COMMENT ON COLUMN manual_chunks.provenance IS 'bronze 血緣：bronze_path / bronze_sha256 / emitted_at（audit_corpus gate 保證完整）';

-- ============================================================================
-- [2] case_entries — 案例史（症狀 → 解法）
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_entries (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    brand           VARCHAR(100),
    model           VARCHAR(100),
    symptom         TEXT NOT NULL,
    resolution      TEXT NOT NULL,
    embedding       vector(768) NOT NULL,           -- embed(symptom)
    embedding_model VARCHAR(100) NOT NULL,
    source_problem_card_id UUID,                    -- 溯源：knowledge_ready 問題卡（Phase D）
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_entries_hnsw
    ON case_entries USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_case_entries_scope
    ON case_entries (tenant_id, brand, model) WHERE is_active AND deleted_at IS NULL;

COMMENT ON TABLE case_entries IS 'RAG 案例史；Phase D 由 knowledge-refinery HITL 灌入（ADR-018）；查詢閾值 similarity ≥ 0.85（ADR-010）';
