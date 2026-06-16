-- 034-role-permissions-tenant-id.sql
--
-- WHY：
--   首次 Cloud Run 部署套 schema 時，prod 既有一張「舊版」role_permissions —— 結構為
--   多對多 join 表 (role_id uuid, permission_id uuid, tenant_id uuid)，與 F-019
--   現行設計 (tenant_id, role_name TEXT, permission_code TEXT, granted ...) 完全不同。
--   故 Schema_rbac_dynamic.sql 的 CREATE TABLE IF NOT EXISTS 被略過、後續索引/約束
--   報 column role_name / tenant_id does not exist。
--
-- WHAT：
--   舊表為空（join 表未使用，現行 RBAC 走 role_service._MATRIX + 本表覆寫）→ 直接
--   DROP 重建為 F-019 spec。安全閥：僅當「舊結構且 0 列」才 drop，非空則 RAISE 中止
--   交人工處理，絕不誤刪資料。已是新版則整段 no-op（idempotent）。
--
-- 影響：RBAC 動態權限「寫自訂角色」需新結構；讀取一向回退 _MATRIX 預設，行為不變。

DO $$
BEGIN
    -- 偵測舊版 join 表：有 role_id 但無 role_name
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'role_permissions' AND column_name = 'role_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'role_permissions' AND column_name = 'role_name'
    ) THEN
        IF (SELECT count(*) FROM role_permissions) = 0 THEN
            DROP TABLE role_permissions;
        ELSE
            RAISE EXCEPTION
                'role_permissions 為舊 join 結構但非空（% 列）——需人工遷移，本 migration 中止',
                (SELECT count(*) FROM role_permissions);
        END IF;
    END IF;
END $$;

-- 重建為 F-019 spec（已是新版則 IF NOT EXISTS 跳過）
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
