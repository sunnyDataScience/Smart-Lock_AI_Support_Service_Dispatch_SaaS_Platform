-- 070-role-assignment-sod.sql
-- WHY（CR-0071 / TI-RBAC-02 / FR-0019 / §4.6.5 SOD-ROLE-ASSIGN）：使用者 role 指派/變更
--   原無任何生產碼（grep `UPDATE users SET role` 零命中 — 只有 role→permission 矩陣端點），
--   是 CR-0038 類假綠。合規要求 role assign 雙人 SoD（propose+approve 不可同人），且 DB 層
--   也要擋（defense-in-depth，即使 service 被繞過）。
-- WHAT：saas.role_assignment 提案表 + role_assign_dual_sign_distinct CHECK（照抄
--   reconciliation_exception 的 exc_dual_sign_distinct 防線）。
CREATE TABLE IF NOT EXISTS saas.role_assignment (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID NOT NULL,
    target_user_id UUID NOT NULL,
    from_role      TEXT,
    to_role        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'proposed'
                     CHECK (status IN ('proposed','approved','rejected','applied','cancelled')),
    proposed_by    UUID NOT NULL,
    proposed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by    UUID,
    approved_at    TIMESTAMPTZ,
    reason         TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- SoD 硬防線：proposer 與 approver 不可同人（DB 層攔截，繞過 service 也擋）
    CONSTRAINT role_assign_dual_sign_distinct
        CHECK (proposed_by IS NULL OR approved_by IS NULL OR proposed_by <> approved_by)
);
CREATE INDEX IF NOT EXISTS idx_role_assignment_tenant_status
    ON saas.role_assignment (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_role_assignment_target
    ON saas.role_assignment (target_user_id);
COMMENT ON TABLE saas.role_assignment IS
  'CR-0071/TI-RBAC-02：role 指派雙人 SoD 提案表（propose+approve 不同人，DB CHECK 硬防）';
