-- ============================================================================
-- 021-gdpr-forget-requests.sql — FR-0053 Phase II MVP: GDPR Right-to-be-Forgotten
-- ============================================================================
-- 目的：客戶 GDPR forget request 兩階段刪除流程審計 + legal-hold 檢查。
--
-- 範圍：
--   1. 新表 saas.forget_request — 主流程狀態機 + cooldown 30 天硬刪
--   2. 不直接 hard delete 既有 users / customers — service 層執行 soft delete
--      （updated_at + display_name='[REDACTED]' + email='[REDACTED]'）
--   3. T+30 天後由 cron 跑 hard delete（本 commit 不接 cron，留下輪）
--
-- 對齊 user-flow Flow S4 mermaid + ADR-0061 DGS service boundary +
-- ADR-PII-002 雙層防線。
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.forget_request (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),

  -- 對象：user_id（消費者）或 employee_id（員工自請 forget）
  subject_user_id     uuid        NOT NULL,
  subject_email       text        NULL,   -- 接收 request 時 capture（hard delete 後參考）

  -- 狀態機（FR-0053 §1 兩階段）
  status              text        NOT NULL DEFAULT 'received' CHECK (status IN (
    'received',           -- T0：剛收到 request，待 legal-hold check
    'legal_hold_denied',  -- legal-hold 衝突（爭議/仲裁/警方）→ 拒絕
    'soft_deleted',       -- T0+: 軟刪 + 金鑰銷毀完成
    'hard_deleted',       -- T+30：硬刪完成（physical delete）
    'cancelled'           -- 客戶撤回 request
  )),

  -- 觸發來源
  requested_by        text        NOT NULL CHECK (requested_by IN (
    'customer_self',  -- 客戶自助（web/LIFF portal）
    'admin',          -- admin 代為提出
    'dpo'             -- DPO 主動清理
  )),

  -- legal-hold 檢查
  legal_hold_reason   text        NULL,    -- 若 status='legal_hold_denied' 必填
  expected_release_at timestamptz NULL,    -- legal hold 預計解除時間（7d 內通知）

  -- 時程
  received_at         timestamptz NOT NULL DEFAULT NOW(),
  soft_deleted_at     timestamptz NULL,
  hard_delete_eligible_at timestamptz NULL,  -- soft_deleted_at + INTERVAL '30 days'
  hard_deleted_at     timestamptz NULL,

  -- audit
  actor_user_id       uuid        NULL,
  notes               text        NULL,

  created_at          timestamptz NOT NULL DEFAULT NOW(),
  updated_at          timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS forget_req_tenant_status_idx
  ON saas.forget_request(tenant_id, status, received_at DESC);

CREATE INDEX IF NOT EXISTS forget_req_subject_idx
  ON saas.forget_request(subject_user_id, status);

-- 硬刪 cron 用：找 soft_deleted 且 hard_delete_eligible_at 已過
CREATE INDEX IF NOT EXISTS forget_req_hard_delete_due_idx
  ON saas.forget_request(hard_delete_eligible_at)
  WHERE status = 'soft_deleted' AND hard_delete_eligible_at IS NOT NULL;

COMMENT ON TABLE saas.forget_request IS
  'FR-0053 GDPR Right-to-be-Forgotten 兩階段刪除流程：'
  'received → legal_hold_denied | soft_deleted → hard_deleted；'
  'soft → hard 強制 30 天 cooldown (BR-PII-001)';
