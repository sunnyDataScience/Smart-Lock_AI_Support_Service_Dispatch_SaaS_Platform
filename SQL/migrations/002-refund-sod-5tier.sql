-- ============================================================================
-- Migration 002 — Refund 三維 SoD + 5-tier (ADR-0040 v2 / BR-REFUND-006 / FR-0014)
-- ----------------------------------------------------------------------------
-- 對齊 frozen spec DDL: docs/architecture/data/ddl-migration-001-init.sql:463
--   saas.refund（tier / refund_class / 三維 SoD + CHECK）
-- 本 repo 現行為 public.refund_requests（雙簽 approval_chain 模型）。本 migration
-- 採「加欄非破壞」策略：在既有表上補 spec 形狀的欄位 + CHECK，舊欄位/舊雙簽流程
-- 全部保留做 legacy 過渡（Never break userspace）。schema 命名整體遷移到 saas.
-- 留待波次 P2（見 docs/_audit/spec-code-gap-audit-2026-06-01.md §5/§8）。
--
-- 這是 spec-alignment P1-B 垂直切片的 DB 部分。forward-only、可重跑（IF NOT EXISTS）。
-- 套用：psql "$POSTGRES_URI" -f SQL/migrations/002-refund-sod-5tier.sql
-- ============================================================================

-- 1. 5-tier 金額分級（伺服器端從 amount 推算，ADR-0040 §97-104，門檻 1k/5k/30k/100k）
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS tier TEXT;

-- 2. refund_class 必填 enum（product/labor/material/travel/inspection）
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS refund_class TEXT;

-- 3. 三維 SoD 行為人（initiator / approver(s) / executor）
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS initiator_user_id UUID;
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS approver_user_ids UUID[] NOT NULL DEFAULT '{}';
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS executor_user_id UUID;

-- 4. audit linkage + config snapshot（ADR-0067 §5 per-transaction snapshot）
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS audit_event_id UUID;
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS config_version_used VARCHAR(32);

-- ----------------------------------------------------------------------------
-- CHECK 約束（用 DO block 包覆，IF NOT EXISTS 語意 — 既存則跳過，可重跑）
-- 注意：現行 legacy row 的新欄位多為 NULL，CHECK 對 NULL 一律放行，不會擋舊資料。
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'refund_requests_tier_chk'
    ) THEN
        ALTER TABLE refund_requests
            ADD CONSTRAINT refund_requests_tier_chk
            CHECK (tier IS NULL OR tier IN ('L1','L2','L3','L4','L5'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'refund_requests_class_chk'
    ) THEN
        ALTER TABLE refund_requests
            ADD CONSTRAINT refund_requests_class_chk
            CHECK (refund_class IS NULL OR refund_class IN
                   ('product','labor','material','travel','inspection'));
    END IF;

    -- 三維 SoD DB 層硬約束（對齊 spec saas.refund §479-480）
    -- initiator 不得出現在 approver 陣列中
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'refund_requests_sod_initiator_chk'
    ) THEN
        ALTER TABLE refund_requests
            ADD CONSTRAINT refund_requests_sod_initiator_chk
            CHECK (initiator_user_id IS NULL OR initiator_user_id <> ALL(approver_user_ids));
    END IF;

    -- executor 不得等於 initiator
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'refund_requests_sod_executor_chk'
    ) THEN
        ALTER TABLE refund_requests
            ADD CONSTRAINT refund_requests_sod_executor_chk
            CHECK (executor_user_id IS NULL OR initiator_user_id IS NULL
                   OR executor_user_id <> initiator_user_id);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Index — 對齊 spec saas.refund §482-483（state 查詢 + WO 反查）
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS refund_tier_idx
    ON refund_requests (tier, created_at DESC);

CREATE INDEX IF NOT EXISTS refund_class_idx
    ON refund_requests (refund_class);

COMMENT ON COLUMN refund_requests.tier IS
    '5-tier 金額分級 L1..L5（伺服器端從 amount 推算，ADR-0040 §97-104）';
COMMENT ON COLUMN refund_requests.refund_class IS
    'product/labor/material/travel/inspection（BR-REFUND-006 必填）';
COMMENT ON COLUMN refund_requests.initiator_user_id IS '三維 SoD 發起人';
COMMENT ON COLUMN refund_requests.approver_user_ids IS '三維 SoD 核准人陣列';
COMMENT ON COLUMN refund_requests.executor_user_id IS '三維 SoD 執行人（系統/金流商）';
