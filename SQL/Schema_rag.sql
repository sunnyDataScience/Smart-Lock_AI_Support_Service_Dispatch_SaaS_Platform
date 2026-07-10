-- ============================================================================
-- RAG 語義層 Schema（WBS 2.2.1 / ADR-010 知識分層）
-- ============================================================================
-- 版本：v1.0
-- 日期：2026-07-09
-- 說明：
--   1. manual_chunks — 逐型號手冊事實語料（唯一事實語料，ADR-010 治理鐵律）
--      灌注來源：knowledge-pipeline storage/corpus/facts.jsonl（bronze-only 紅線，
--      provenance 帶 bronze 檔 + sha256），經 rag/ingest.py 冪等 upsert。
--   2. case_entries — 案例史（症狀→解法）。表由 Schema.sql（kb-v2 形狀）擁有，
--      併形欄位見 migrations/095（CR-0140；業主裁決 2026-07-10）——本檔只補向量索引。
--      Phase D（knowledge-refinery，ADR-018）HITL 精煉後由 Publisher 灌入。
--   3. 檢索：768 維（實際預設 multilingual-002，CR-0124 勘誤）HNSW cosine；
--      查詢 WHERE 必帶 tenant_id（ADR-010：default deny）。
-- 依賴：pgvector extension（品牌庫 image = pgvector/pgvector:pg17，已內建）
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- [1] rag_manual_chunks — 手冊事實語料
-- ============================================================================
-- ⚠ 原名 manual_chunks 與 Schema.sql:328 的 kb-v2 表（manuals FK 子表，PDF 章節塊）
-- 撞名，CREATE IF NOT EXISTS 對正規 bootstrap 的庫恆 no-op —— RAG 主表從未真正
-- 存在（CR-0142 查實，與 CR-0140 case_entries 同型事故）。兩者語意不同不可併形
-- → 改名 rag_manual_chunks 自持；正式定義在 migrations/096（此處同步供全新庫）。

CREATE TABLE IF NOT EXISTS rag_manual_chunks (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    chunk_id        VARCHAR(32) NOT NULL,          -- knowledge-pipeline 冪等 id（sha256[:16]）
    brand           VARCHAR(100) NOT NULL,          -- 'general' = 跨品牌通用
    model           VARCHAR(100) NOT NULL DEFAULT 'general',
    category        VARCHAR(50),                    -- setup / troubleshoot / specification / knowledge / manual
    content         TEXT NOT NULL,
    embedding       vector(768) NOT NULL,           -- RAG_EMBED_MODEL（預設 multilingual-002，CR-0124 勘誤）
    embedding_model VARCHAR(100) NOT NULL,          -- 記錄產生 embedding 的模型（重嵌可辨識）
    source_type     VARCHAR(50),                    -- youtube / video / website / references
    source          TEXT,
    provenance      JSONB NOT NULL DEFAULT '{}',    -- bronze_path / bronze_sha256 / emitted_at
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, chunk_id)
);

-- 語義檢索主索引（cosine）
CREATE INDEX IF NOT EXISTS idx_rag_manual_chunks_hnsw
    ON rag_manual_chunks USING hnsw (embedding vector_cosine_ops);
-- 結構過濾（tenant + 品牌/型號 gating）
CREATE INDEX IF NOT EXISTS idx_rag_manual_chunks_scope
    ON rag_manual_chunks (tenant_id, brand, model) WHERE is_active;

COMMENT ON TABLE rag_manual_chunks IS 'RAG 事實語料（輔助語義查找，ADR-030）；灌注自 knowledge-pipeline facts.jsonl 與 lockcore references，bronze-only';
COMMENT ON COLUMN rag_manual_chunks.chunk_id IS 'knowledge-pipeline 冪等 chunk id；(tenant_id, chunk_id) 唯一，重灌 upsert';
COMMENT ON COLUMN rag_manual_chunks.provenance IS 'bronze 血緣：bronze_path / bronze_sha256 / emitted_at（audit_corpus gate 保證完整）';

-- ============================================================================
-- [2] case_entries — 案例史向量索引
-- ============================================================================
-- ⚠ 表由 Schema.sql 擁有（kb-v2 形狀：title/problem_description/solution）。
-- 舊版本檔曾在此重複 CREATE TABLE（rag 形狀 symptom/resolution），因 IF NOT EXISTS
-- 於真實庫 no-op 形成潛在缺陷（CR-0124；rag 查詢 SQL ERROR 被 fail-soft 遮蔽）。
-- 業主裁決 2026-07-10（CR-0139 §8-1→B 併形）：撤重複 CREATE；
-- 併形欄位（source_problem_card_id / embedding_model）在 migrations/095。
-- rag 檢索改讀 kb 欄名（problem_description AS symptom, solution AS resolution），
-- MCP 工具輸出鍵不變。

CREATE INDEX IF NOT EXISTS idx_case_entries_hnsw
    ON case_entries USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_case_entries_scope
    ON case_entries (tenant_id, brand, model) WHERE is_active AND deleted_at IS NULL;

COMMENT ON TABLE case_entries IS '知識庫案例史（kb-v2 形狀＋095 併形欄）；Phase D 由 knowledge-refinery HITL 灌入（ADR-018）；rag 查詢閾值 similarity ≥ 0.85（ADR-010）';
