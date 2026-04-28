-- ============================================================================
-- Schema_api_phase1.sql — Admin REST API（api/）Phase 1 MVP 所需 schema
-- ============================================================================
--
-- 適用範圍：補齊 18 個 Phase 1 endpoints 所需資料表。
-- 安全性：全為 IF NOT EXISTS / ADD COLUMN IF NOT EXISTS，可重複執行（idempotent）。
--
-- 變更摘要：
-- 1. users          : 新增 tenant_id、password_hash 欄位
-- 2. case_entries   : 新增 tenant_id、tags、verified、model、embedding_status
-- 3. revoked_jti    : 新建（JWT 撤銷清單）
-- 4. idempotency_keys: 新建（24h 寫操作去重）
-- 5. notifications  : 新建（站內通知）
-- 6. system_config  : 新建（單列系統設定，JSONB 主體）
-- ============================================================================

-- 預設 tenant（MVP：所有現有資料先掛到 default tenant；後續多租戶展開時再分流）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto') THEN
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
    END IF;
END $$;


-- ─────────────────────────────────────────────────────────────────────────
-- [1] users 補欄位
-- ─────────────────────────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- 補設預設 tenant_id（供現有 row）
UPDATE users
SET tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
WHERE tenant_id IS NULL;

-- 強制非 NULL（資料補完後）
ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE users ALTER COLUMN tenant_id SET DEFAULT '00000000-0000-0000-0000-000000000001'::uuid;

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email_tenant ON users(tenant_id, email) WHERE email IS NOT NULL;

COMMENT ON COLUMN users.tenant_id IS '所屬租戶 ID（多租戶隔離鍵）；admin/technician 帳號必填';
COMMENT ON COLUMN users.password_hash IS 'bcrypt password hash；僅供 admin/technician 帳號登入；line_user 為 NULL';


-- ─────────────────────────────────────────────────────────────────────────
-- [2] case_entries 對齊 OpenAPI CaseEntry schema
-- ─────────────────────────────────────────────────────────────────────────
ALTER TABLE case_entries ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE case_entries ADD COLUMN IF NOT EXISTS model VARCHAR(100);  -- OpenAPI 用 model（DB 既有 lock_type 視為 legacy）
ALTER TABLE case_entries ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT ARRAY[]::TEXT[];
ALTER TABLE case_entries ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;
ALTER TABLE case_entries ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) DEFAULT 'pending';
                                              -- 'pending' | 'ready' | 'failed'

UPDATE case_entries
SET tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
WHERE tenant_id IS NULL;

ALTER TABLE case_entries ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE case_entries ALTER COLUMN tenant_id SET DEFAULT '00000000-0000-0000-0000-000000000001'::uuid;

CREATE INDEX IF NOT EXISTS idx_cases_tenant_active ON case_entries(tenant_id, is_active, created_at DESC);


-- ─────────────────────────────────────────────────────────────────────────
-- [3] revoked_jti — JWT 撤銷清單（logout）
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS revoked_jti (
    jti         UUID PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revoked_jti_expires ON revoked_jti(expires_at);

COMMENT ON TABLE revoked_jti IS 'JWT 撤銷清單；過期後（expires_at < now）可清除';


-- ─────────────────────────────────────────────────────────────────────────
-- [4] idempotency_keys — 24h 寫操作去重
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS idempotency_keys (
    tenant_id        UUID NOT NULL,
    key              TEXT NOT NULL,
    method           TEXT NOT NULL,
    path             TEXT NOT NULL,
    request_hash     TEXT NOT NULL,
    response_status  INTEGER NOT NULL,
    response_body    JSONB NOT NULL,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, key)
);
CREATE INDEX IF NOT EXISTS idx_idem_created ON idempotency_keys(created_at);

COMMENT ON TABLE idempotency_keys IS '24h 寫操作去重；clients 重送同 key + 同 hash 直接回放';


-- ─────────────────────────────────────────────────────────────────────────
-- [5] notifications — 站內通知
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(50) NOT NULL,
                    -- 對應 openapi.yaml NotificationType:
                    -- 'work_order_assigned' | 'work_order_status_changed' | 'sla_alert'
                    -- 'refund_requested' | 'dispute_opened' | 'inventory_low_stock'
                    -- 'rbac_updated' | 'manual'
    severity        VARCHAR(20) DEFAULT 'info',
                    -- 'info' | 'warning' | 'critical'
    title           VARCHAR(255) NOT NULL,
    body            TEXT,
    source          VARCHAR(50) DEFAULT 'system',
                    -- 'system' | 'agent' | 'admin'
    related_entity  JSONB,                          -- {type, id, label}
    actions         JSONB DEFAULT '[]'::jsonb,      -- [{label, action, url}]
    raw_event_id    UUID,
    read_at         TIMESTAMP WITH TIME ZONE,
    archived_at     TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notif_user_unread ON notifications(user_id, read_at NULLS FIRST, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notif_tenant ON notifications(tenant_id, created_at DESC);

COMMENT ON TABLE notifications IS '站內通知（每用戶可見）；對齊 openapi.yaml Notification schema';


-- ─────────────────────────────────────────────────────────────────────────
-- [6] system_config — 系統設定（單一 row 即可，但用 tenant_id 隔離）
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_config (
    tenant_id   UUID PRIMARY KEY,
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
                -- 鍵：rag, llm, resolution, line_bot（對齊 openapi.yaml SystemConfig schema）
    version     INTEGER NOT NULL DEFAULT 1,         -- 樂觀鎖
    updated_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE system_config IS '系統設定（per-tenant 單列）；version 提供樂觀鎖';


-- ─────────────────────────────────────────────────────────────────────────
-- [7] technicians 補欄位（registerTechnician 需要 capabilities/regions）
-- ─────────────────────────────────────────────────────────────────────────
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS tenant_id UUID;
UPDATE technicians SET tenant_id = '00000000-0000-0000-0000-000000000001'::uuid WHERE tenant_id IS NULL;
ALTER TABLE technicians ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE technicians ALTER COLUMN tenant_id SET DEFAULT '00000000-0000-0000-0000-000000000001'::uuid;
CREATE INDEX IF NOT EXISTS idx_technicians_tenant ON technicians(tenant_id);
