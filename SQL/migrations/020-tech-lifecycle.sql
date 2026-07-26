-- ============================================================================
-- migrate-targets: brand,tech  (LOCK-62 item3 補正：saas.technician_lifecycle_event 技師庫 saas schema 實存)
-- 020-tech-lifecycle.sql — FR-0044 Phase II MVP: Technician Lifecycle
-- ============================================================================
-- 目的：師傅 onboarding / suspend / reactivate / terminate 完整生命週期
--      audit trail + 狀態機擴展。
--
-- 範圍：
--   1. technicians.status enum 擴 'rejected' / 'terminated' 兩個終態
--   2. 新表 saas.technician_lifecycle_event 記錄每次狀態變動 + 原因 + actor
--
-- 對齊既有 technicians.status: pending_approval / active / inactive /
-- suspended → 擴 rejected / terminated 完整 lifecycle
-- ============================================================================

-- 1. 不直接 ALTER technicians.status CHECK（v1 schema 未顯式 CHECK），
--    service 層自驗 enum。本 migration 純加 audit 表。

-- 2. 新表：lifecycle event audit
CREATE TABLE IF NOT EXISTS saas.technician_lifecycle_event (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  technician_id       uuid        NOT NULL,            -- public.technicians.id plain ref

  event_type          text        NOT NULL CHECK (event_type IN (
    'onboarding_approved',   -- pending_approval → active
    'onboarding_rejected',   -- pending_approval → rejected
    'suspended',             -- active → suspended
    'reactivated',           -- suspended → active
    'terminated',            -- 任何 → terminated（終態）
    'rating_threshold_breach',  -- 自動觸發；rating < threshold 但未自動 suspend
    'cert_expired'           -- 自動觸發；證照過期但未自動 suspend
  )),

  previous_status     text        NULL,                 -- 變更前 status
  new_status          text        NULL,                 -- 變更後 status (terminate 時 = 'terminated')

  reason              text        NOT NULL,
  notes               text        NULL,

  -- actor 審計
  actor_user_id       uuid        NULL,                 -- NULL 為系統自動觸發
  actor_role          text        NULL,                 -- 'admin' / 'operations_manager' / 'system'

  created_at          timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS tle_tenant_tech_created_idx
  ON saas.technician_lifecycle_event(tenant_id, technician_id, created_at DESC);

CREATE INDEX IF NOT EXISTS tle_event_type_idx
  ON saas.technician_lifecycle_event(event_type, created_at DESC);

COMMENT ON TABLE saas.technician_lifecycle_event IS
  'FR-0044 師傅 lifecycle audit：onboarding / suspend / reactivate / '
  'terminate 等狀態變動歷史，含 actor + 原因。';

COMMENT ON COLUMN saas.technician_lifecycle_event.event_type IS
  'onboarding_approved/rejected: pending → active/rejected; '
  'suspended/reactivated: active ↔ suspended; '
  'terminated: 任何 → terminated 終態；'
  'rating_threshold_breach / cert_expired: 自動偵測事件，未直接改 status';
