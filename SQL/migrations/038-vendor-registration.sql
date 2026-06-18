-- 038-vendor-registration.sql
--
-- WHY（CR-0029 / 2026-06-17 會議 Action #3）：
--   平台要變「外包仲介」：發案者（品牌商/鎖店/經銷商）與接案者（師傅）兩路註冊。
--   現行只有師傅 self-register（auth_service.register_technician），無廠商/品牌商註冊路由與主表。
--   會議定調本輪先 single-tenant 可逆版（預留 tenant_type），multi-tenant 三類租戶留 CR-0031。
--
-- WHAT：
--   (1) vendors 主表（發案者：brand/locksmith/distributor）—— 對應 technicians（接案者）。
--   (2) users.tenant_type（requestor/technician/platform；single-tenant 可 NULL，為 CR-0031 預留）。
--   (3) 既有 users backfill tenant_type（technician→technician、後台角色→platform、line_user→NULL）。
--   列舉值由 app 層驗證（不加 DB CHECK 保彈性）；email 全域唯一沿用既有規則。
--
-- 影響：純新增表 + nullable 欄，idempotent；tenant_id 預留同 migration 036/037 模式。

-- 1. 發案者主表
CREATE TABLE IF NOT EXISTS vendors (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vendor_type     VARCHAR(30) NOT NULL,           -- brand/locksmith/distributor（app 驗證）
    name            VARCHAR(150) NOT NULL,
    company_name    VARCHAR(150),
    phone           VARCHAR(50) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    address         TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending_approval',  -- pending_approval/active/suspended/rejected
    rejection_reason TEXT,
    approved_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at     TIMESTAMP WITH TIME ZONE,
    tenant_id       UUID,                            -- multi-tenant 預留（CR-0031）
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vendors_email  ON vendors (email);
CREATE INDEX IF NOT EXISTS idx_vendors_status ON vendors (status);
CREATE INDEX IF NOT EXISTS idx_vendors_tenant ON vendors (tenant_id) WHERE tenant_id IS NOT NULL;

-- 2. users.tenant_type（單租戶可 NULL；CR-0031 三類租戶用）
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_type VARCHAR(30);

-- 3. 既有 users backfill tenant_type（接案者/平台後台；line_user 消費者留 NULL）
UPDATE users SET tenant_type = 'technician'
    WHERE role = 'technician' AND tenant_type IS NULL;
UPDATE users SET tenant_type = 'platform'
    WHERE role IN ('admin','reviewer','operations_manager','dispatcher','customer_service')
      AND tenant_type IS NULL;

COMMENT ON TABLE  vendors IS 'CR-0029 發案者主表（品牌商/鎖店/經銷商）；對應 technicians 接案者；status pending_approval→active';
COMMENT ON COLUMN vendors.vendor_type IS 'brand/locksmith/distributor（app 驗證）';
COMMENT ON COLUMN users.tenant_type   IS 'requestor/technician/platform（CR-0031 三類租戶預留；single-tenant 可 NULL）';
