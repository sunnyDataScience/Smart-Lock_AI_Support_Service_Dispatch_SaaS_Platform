-- 049-exception-framework.sql
-- CR-0041 M15 異常框架（BR-M15-01 異常實體 + return_path / BR-M15-03 high-risk pause）。
--
-- WHY：缺料/改期/加價拒絕/取消/退款/爭議/安全風險等異常不能藏在 chat（會議+spec）。
--   generated.py 已設計 Exception model 但無 DB 表/service。approval inbox（FR-0049）已聚合
--   scope_change/refund/dispute/reschedule，但不涵蓋無專屬表的異常（no_show/material_shortage 等）。
--
-- WHAT：saas.exception_case（control tower，對齊 generated.py model + BR-M15-01 return_path action）
--   + work_orders.high_risk_hold 旗標（HD-2：不改主狀態機，dispatch/complete gate 檢查；exception resolved 解除）。
--
-- 性質：新表 + ADD COLUMN，idempotent 可重套。

CREATE TABLE IF NOT EXISTS saas.exception_case (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    work_order_id   UUID,
    exception_type  VARCHAR(40) NOT NULL,   -- ExceptionType 10 值（app 層驗證，對齊 generated.py）
    status          VARCHAR(20) NOT NULL DEFAULT 'open',
    severity        VARCHAR(12) NOT NULL DEFAULT 'medium',
    description     TEXT,
    return_path     VARCHAR(20),            -- BR-M15-01 9 動作：continue/requote/reschedule/reassign/new_wo/cancel/refund/rma/dispute
    return_to_stage VARCHAR(40),            -- generated.py：處理後返回的 WO 狀態
    triggers_circuit_breaker BOOLEAN NOT NULL DEFAULT FALSE,
    actor_type      VARCHAR(20),
    actor_id        VARCHAR(100),
    resolution      TEXT,
    resolved_at     TIMESTAMPTZ,
    resolved_by     UUID,
    created_by      UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT exception_status_chk
        CHECK (status IN ('open', 'investigating', 'resolved', 'escalated', 'closed')),
    CONSTRAINT exception_severity_chk
        CHECK (severity IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX IF NOT EXISTS idx_exception_case_tenant_status
    ON saas.exception_case (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exception_case_wo
    ON saas.exception_case (work_order_id);

-- BR-M15-03 high-risk pause（HD-2）：WO 旗標，dispatch/complete gate 檢查；exception resolved 解除。
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS high_risk_hold BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON TABLE saas.exception_case IS
    'CR-0041 M15 異常 control tower：缺料/改期/加價拒絕/取消/退款/爭議/安全風險統一追蹤 + return_path';
COMMENT ON COLUMN work_orders.high_risk_hold IS
    'CR-0041 BR-M15-03：high-risk 異常暫停旗標；TRUE 時擋 dispatch/complete，待 exception resolved 解除';
