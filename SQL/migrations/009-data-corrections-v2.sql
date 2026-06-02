-- =============================================================================
-- 009-data-corrections-v2.sql
-- Track B S5 — data_corrections tenant-scoped review queue（CR-0004 §8 / ADR-0029）
--
-- 決議（CR-0004 §8 HD-1~HD-5）：
--   HD-1: 方案 B 就地補 tenant_id（ALTER TABLE ADD COLUMN）
--   HD-2: 補 resolved 第四態（pending/approved/resolved/rejected）
--   HD-3: approve 只改 status，SOP draft 自動建立延 phase 2（follow-up）
--   HD-4: approve/reject/resolve 需 admin（service 層驗 RBAC）
--   HD-5: GDPR conversation_context/user_facts PII → 標 follow-up（FR-0053）
--   ADR-0030: agent harness 寫入須同步補 tenant_id
--
-- 冪等：可重複執行。
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/009-data-corrections-v2.sql
-- =============================================================================

-- ── Step 1: 確保 data_corrections 表存在（對齊 agent/harness/data_correction.py:68 欄位 + 型別）
CREATE TABLE IF NOT EXISTS data_corrections (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             TEXT NOT NULL,
    note                TEXT DEFAULT '',
    conversation_context TEXT NOT NULL DEFAULT '',
    user_facts          JSONB,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Step 2: 補 review 稽核欄（原 _ensure_review_columns lazy 補，現由 migration 保證存在）
ALTER TABLE data_corrections
    ADD COLUMN IF NOT EXISTS reviewed_by   TEXT,
    ADD COLUMN IF NOT EXISTS reviewed_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_note   TEXT;

-- ── Step 3: 方案 B 核心 — 補 tenant_id 欄
ALTER TABLE data_corrections
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- ── Step 4: Backfill 既有 NULL tenant 列 → dev tenant
UPDATE data_corrections
   SET tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
 WHERE tenant_id IS NULL;

-- ── Step 5: 補原有 harness index（idempotent）
CREATE INDEX IF NOT EXISTS idx_dc_user_id
    ON data_corrections (user_id);

CREATE INDEX IF NOT EXISTS idx_dc_status
    ON data_corrections (status);

-- ── Step 6: tenant-scoped 複合 index（v2 list query 主路徑）
CREATE INDEX IF NOT EXISTS idx_dc_tenant_status_created
    ON data_corrections (tenant_id, status, created_at DESC);

-- ── Note（HD-5 / FR-0053）：
--   conversation_context / user_facts 含 PII（LINE user_id、對話內容、user facts）。
--   two-phase delete / legal_hold 留 FR-0053 獨立實作，本波次不做。
--   status CHECK constraint 不強加（避免與 legacy lazy 列衝突；v2 service 層驗 _VALID_STATUSES）。
