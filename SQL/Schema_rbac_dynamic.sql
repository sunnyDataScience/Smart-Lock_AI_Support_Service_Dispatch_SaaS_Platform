-- F-019 RBAC 動態調整 — role_permissions 表
--
-- WHY：
--   目前 5 系統角色的權限矩陣在 api/services/role_service.py 寫死（_MATRIX）；
--   F-019 需要 admin / tenant_admin 在 runtime 修改某角色的權限，
--   且變更後 5 秒內透過 /realtime/rbac WS 推送給所有相關 session。
--
-- 設計：
--   role_permissions 為 SCD Type 1（直接覆寫，最後狀態為準），
--   完整修改歷史走 audit_events（event_type=admin_action,
--   action=role.permissions_updated）— 該表已有 payload.before / after。
--
--   permission_code 採扁平字串 `resource.action`，與 OpenAPI
--   RolePermissionsUpdateRequest.permissions 格式一致：
--     work_orders.read / work_orders.write / work_orders.delete / ...
--
--   role_name 不外鍵 — 5 系統角色 + dispatcher / customer_service 等都允許，
--   軟限制由 service 層的白名單驗證。

CREATE TABLE IF NOT EXISTS role_permissions (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID        NOT NULL,
    role_name       TEXT        NOT NULL,
    permission_code TEXT        NOT NULL,
    granted         BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_by      UUID,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, role_name, permission_code)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_tenant_role
    ON role_permissions (tenant_id, role_name);

-- 註：本表「不存在記錄」= 該 role 對該 permission_code 的授權回退到
-- _MATRIX 的預設值；存在記錄則以 granted 欄位為準。
