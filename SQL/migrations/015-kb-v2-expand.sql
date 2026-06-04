-- ============================================================================
-- Migration 015 — KB v2 expand（CR-0005 / ADR-0103 / FR-KB-002~003）
-- ----------------------------------------------------------------------------
-- 業主 2026-06-04 拍 CR-0005 §8：
--   HD-01 = (a) 保留 meta-wrapping 響應 shape（與 ADR-0101 對齊）
--   HD-02 = (a) DELETE 軟刪（加 deleted_at；GET list 預設過濾 NULL）
--   HD-03 = (a) audit log 寫 DB 表 kb_audit_log（actor + diff + before/after）
--   HD-04 = (a) virus scan 同步 ClamAV（schema 不變，由 service 層整合）
--   HD-05 = (a) search cosine similarity desc（schema 不變，service 層 ORDER BY）
--   HD-06 = open（export 格式預設未裁，schema 不影響）
--
-- 本 migration 對應 HD-02 + HD-03：DDL 變動。
-- HD-04/05 由 service 層處理（無 schema 影響）。
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/015-kb-v2-expand.sql
-- Idempotent: ALTER TABLE ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. case_entries / manuals 加 deleted_at（HD-02 軟刪）
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE case_entries
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_case_entries_active
    ON case_entries(tenant_id, created_at DESC)
    WHERE deleted_at IS NULL;     -- GET list 預設過濾的 partial index

ALTER TABLE manuals
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_manuals_active
    ON manuals(tenant_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. kb_audit_log 表（HD-03 寫 DB 表）
--    記每次 KB 文件變更（PUT/DELETE）的 actor + diff + before/after
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS saas.kb_audit_log (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid        NOT NULL REFERENCES saas.tenant(id),

    -- 目標
    doc_id          uuid        NOT NULL,
    doc_type        text        NOT NULL CHECK (doc_type IN ('case', 'manual')),

    -- 操作
    action          text        NOT NULL CHECK (action IN ('create', 'update', 'delete', 'restore')),

    -- 變更內容（HD-03 完整 before/after）
    before_state    jsonb       NULL,     -- 操作前快照（create 時為 NULL）
    after_state     jsonb       NULL,     -- 操作後快照（delete 時為 NULL）
    diff            jsonb       NULL,     -- 計算後的 diff（service 寫入，optional）

    -- Audit（actor 採 plain uuid 比照 dispute.filed_by 設計）
    actor_user_id   uuid        NOT NULL,
    actor_role      text        NOT NULL,
    actor_ip        text        NULL,     -- 可選紀錄
    user_agent      text        NULL,     -- 可選紀錄

    -- 時間
    created_at      timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_audit_log_tenant_doc
    ON saas.kb_audit_log(tenant_id, doc_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kb_audit_log_actor
    ON saas.kb_audit_log(actor_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kb_audit_log_action_recent
    ON saas.kb_audit_log(tenant_id, action, created_at DESC)
    WHERE created_at > (NOW() - INTERVAL '90 days');  -- 90 天熱資料 partial index

-- ─────────────────────────────────────────────────────────────────────────────
-- 註記：HD-04 virus scan
--   不需 schema 變動。manuals 既有 status 欄（processing/ready/failed）已支援。
--   service 層 upload_manual 流程：
--     1. 接 multipart bytes
--     2. 同步呼叫 ClamAV（HD-04=a）— 失敗即 raise
--     3. 過關後寫 storage + INSERT manuals status='ready'
--   ClamAV daemon 由 prod infra 提供（sidecar / external endpoint），dev 環境可
--   透過 env CLAMAV_HOST 配置；缺值時 service 層 fail-soft（log warn + skip）。
-- ============================================================================

-- ============================================================================
-- 註記：HD-05 search 預設排序
--   不需 schema 變動。case_entries.embedding + manuals.embedding 既有 pgvector
--   ivfflat index 可重用。service 層 search 預設 ORDER BY embedding <=> query_vec ASC
--   （cosine distance 升序 = similarity 降序）。
-- ============================================================================
