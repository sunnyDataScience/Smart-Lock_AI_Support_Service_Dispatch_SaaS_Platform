-- ============================================================================
-- Migration 014 — Reschedule Proposals（CR-0007 / FR-0009 / FR-0011-RSVP / ADR-0105）
-- ----------------------------------------------------------------------------
-- 業主 2026-06-04 拍 CR-0007 §8：
--   HD-01=(a) door-check 強制 arrival 前置（狀態機限制）
--   HD-02=(a) proposed_slots 上限 1-3
--   HD-03=(a) 客戶回應 SLA 24h
--   HD-04=(a) 獨立表 reschedule_proposals（清楚 lineage）
--   HD-05=(a) door-check checklist freeform jsonb（無 BE schema 驗證）
--
-- 設計：
--   - saas.reschedule_proposal（tenant-scoped via work_order JOIN）
--   - proposed_slots jsonb array（1-3 items，由 service 層驗證）
--   - status 機：pending → customer_confirmed | customer_rejected | expired
--   - sla_deadline = NOW() + INTERVAL '24 hours'（HD-03）
--   - response_time 計算：customer_chosen_at - created_at
--   - actor_user_id 採 plain uuid NOT NULL，比照 migration 008 設計
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/014-reschedule-proposals.sql
-- Idempotent: CREATE TABLE IF NOT EXISTS / index IF NOT EXISTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.reschedule_proposal (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id   uuid        NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id       uuid        NOT NULL REFERENCES saas.tenant(id),

    -- 提案內容（HD-04 獨立表 + HD-02 上限 1-3 由 service 驗）
    proposed_slots  jsonb       NOT NULL,                   -- [{slot_index, start, end}, ...]
    message_to_customer text    NULL,
    send_via        text        NOT NULL DEFAULT 'line' CHECK (send_via IN ('line', 'sms', 'email')),

    -- 狀態 + SLA（HD-03 = 24h）
    status          text        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'customer_confirmed', 'customer_rejected', 'expired')),
    sla_deadline    timestamptz NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),

    -- 客戶回應
    chosen_slot_index integer   NULL,        -- 0-based index into proposed_slots
    rejection_reason  text      NULL,
    customer_responded_at timestamptz NULL,

    -- Audit
    proposed_by_user_id uuid    NOT NULL,    -- plain uuid（與 dispute.filed_by 同設計）
    proposed_by_role    text    NOT NULL CHECK (proposed_by_role IN ('technician', 'operations_manager', 'admin')),
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    updated_at      timestamptz NOT NULL DEFAULT NOW(),

    -- HD-02 上限檢查（DB 層輔助保護；主驗證在 service）
    CONSTRAINT proposed_slots_max_3 CHECK (jsonb_array_length(proposed_slots) BETWEEN 1 AND 3)
);

CREATE INDEX IF NOT EXISTS idx_reschedule_proposal_work_order
    ON saas.reschedule_proposal(work_order_id);

CREATE INDEX IF NOT EXISTS idx_reschedule_proposal_tenant_status
    ON saas.reschedule_proposal(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_reschedule_proposal_sla_pending
    ON saas.reschedule_proposal(sla_deadline)
    WHERE status = 'pending';   -- cron 用：找 expired 候選

-- 觸發 updated_at 自動同步
CREATE OR REPLACE FUNCTION saas._touch_reschedule_proposal_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reschedule_proposal_updated_at ON saas.reschedule_proposal;
CREATE TRIGGER trg_reschedule_proposal_updated_at
    BEFORE UPDATE ON saas.reschedule_proposal
    FOR EACH ROW EXECUTE FUNCTION saas._touch_reschedule_proposal_updated_at();

-- ============================================================================
-- 註記：door-check 強制 arrival 前置（HD-01）
--   不需 schema 變動；走 work_order_events 既有 'arrival' / 'door_check' 兩 event_type
--   service 層在 record_door_check_v2 前查 work_order_events WHERE event_type='arrival'
--   不存在 → raise ApiError("STATE_CONFLICT", ..., 409)
-- ============================================================================

-- ============================================================================
-- 註記：HD-05 door-check checklist freeform jsonb
--   既有 work_order_events.payload jsonb 已支援，無 schema 變動
--   service 層不驗證 checklist 內部結構（freeform），只驗 payload 是 dict
-- ============================================================================
