-- ============================================================================
-- Migration 001 — Cancellation 6-Stage v2 (ADR-0102 / FR-0052 / BR-CANCEL-001..008)
-- ----------------------------------------------------------------------------
-- 對齊 frozen spec DDL: docs/architecture/data/ddl-migration-001-init.sql:445
--   saas.cancellation
-- 本 repo 現行為 public schema（非 saas.）— 表名/欄位對齊 spec，schema 命名
-- 整體遷移留待波次 P2（見 docs/_audit/spec-code-gap-audit-2026-06-01.md §5/§8 C-10）。
--
-- 這是 spec-alignment 第一個 vertical slice 的 DB 部分。forward-only。
-- 套用：psql "$POSTGRES_URI" -f SQL/migrations/001-cancellation-6stage.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS cancellation (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL,
    work_order_id       UUID NOT NULL REFERENCES work_orders(id) ON DELETE RESTRICT,
    -- 6 階段（對齊 spec enum；S1.5 在 SQL 以 S1_5 表示）
    cancellation_stage  VARCHAR(8) NOT NULL
                        CHECK (cancellation_stage IN ('S1','S1_5','S2','S3','S4','S5')),
    initiator_role      VARCHAR(32) NOT NULL
                        CHECK (initiator_role IN ('customer','customer_service','technician','system_auto')),
    reason_code         VARCHAR(64) NOT NULL,           -- FK 由 app 層對 config namespace 驗證 (ADR-0102 §B)
    customer_fee        NUMERIC(12,2) NOT NULL DEFAULT 0,
    travel_fee          NUMERIC(12,2) NOT NULL DEFAULT 0,
    technician_penalty  NUMERIC(12,2),                  -- 師傅 initiated 累犯 (ADR-0102 §C)
    goodwill_waiver     BOOLEAN NOT NULL DEFAULT FALSE,
    audit_event_id      UUID NOT NULL,                  -- SoD 三維行為人記於 audit payload (ADR-0102 §D)
    config_version_used VARCHAR(32) NOT NULL,           -- ADR-0067 §5 per-transaction snapshot
    note                TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS cancel_wo_idx
    ON cancellation (work_order_id);

CREATE INDEX IF NOT EXISTS cancel_tenant_stage_idx
    ON cancellation (tenant_id, cancellation_stage, created_at);

-- 師傅 initiated 累犯月計數需 join work_orders.technician_id；此 index 加速
CREATE INDEX IF NOT EXISTS cancel_reason_created_idx
    ON cancellation (reason_code, created_at);
