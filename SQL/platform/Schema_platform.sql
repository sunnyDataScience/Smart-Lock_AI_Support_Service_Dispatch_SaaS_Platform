-- ═══════════════════════════════════════════════════════════════════════════
-- Schema_platform.sql — 平台庫(lock_platform)schema(CR-0114)
--
-- 平台方(Lock AI)console 自有資料,與品牌庫/技師庫物理分離:
--   [1] users              : 平台管理員帳號(role='platform_admin';欄位子集對齊
--                            品牌 users,使 core/auth.py 的安全狀態/lockout 查詢可共用)
--   [2] revoked_jti        : 平台 token 撤銷清單(登出/refresh rotate)
--   [3] brand_applications : 品牌廠商鎖店的平台使用申請(landing 公開表單;
--                            意向書 —— 不建帳號、不收密碼,核准後人工開站)
--
-- 慣例:全部 IF NOT EXISTS,可重複套用(由 scripts/db/init-platform-db.sh 執行)。
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────
-- [1] users — 平台管理員帳號
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name           VARCHAR(255),
    email                  VARCHAR(255) NOT NULL UNIQUE,
    phone                  VARCHAR(50),
    password_hash          TEXT NOT NULL,
    role                   VARCHAR(50) NOT NULL DEFAULT 'platform_admin',
    is_active              BOOLEAN NOT NULL DEFAULT TRUE,
    -- A1/A2/A3 帳號安全欄位(與品牌庫 migration 084 對齊,core/auth.py 共用查詢)
    failed_login_attempts  INT NOT NULL DEFAULT 0,
    locked_until           TIMESTAMP WITH TIME ZONE,
    password_changed_at    TIMESTAMP WITH TIME ZONE,
    created_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS '平台管理員帳號(platform_admin);與品牌/師傅 user pool 物理分離(CR-0114)';
COMMENT ON COLUMN users.role IS '固定 platform_admin;平台庫不承載品牌角色';

-- ─────────────────────────────────────────────────────────────────────────
-- [2] revoked_jti — 平台 JWT 撤銷清單
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS revoked_jti (
    jti         UUID PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_platform_revoked_jti_expires ON revoked_jti(expires_at);

COMMENT ON TABLE revoked_jti IS '平台 token 撤銷清單;過期後(expires_at < now)可清除';

-- ─────────────────────────────────────────────────────────────────────────
-- [3] brand_applications — 品牌申請(CR-0114 R2)
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS brand_applications (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_type  VARCHAR(20) NOT NULL
                      CHECK (application_type IN ('brand','locksmith','distributor')),
    company_name      VARCHAR(150) NOT NULL,
    contact_name      VARCHAR(150) NOT NULL,
    tax_id            VARCHAR(8)  NOT NULL CHECK (tax_id ~ '^\d{8}$'),
    phone             VARCHAR(20) NOT NULL CHECK (phone ~ '^09\d{8}$'),
    email             VARCHAR(255) NOT NULL,
    address           TEXT,
    notes             TEXT,                             -- 申請人留言
    status            VARCHAR(20) NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','approved','rejected')),
    slug              VARCHAR(30),                      -- 核准時定案的品牌代號(部署參數用)
    review_notes      TEXT,
    reviewed_by       UUID REFERENCES users(id),        -- 平台管理員
    reviewed_at       TIMESTAMP WITH TIME ZONE,
    submitted_ip      VARCHAR(64),                      -- 公開表單來源 IP(限流依據)
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 同一 email 同時只能有一件待審申請(核准/拒絕後可再申請)
CREATE UNIQUE INDEX IF NOT EXISTS uq_brand_app_pending_email
    ON brand_applications(email) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_brand_app_status_created
    ON brand_applications(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_brand_app_ip_created
    ON brand_applications(submitted_ip, created_at DESC);

COMMENT ON TABLE brand_applications IS '品牌廠商鎖店平台使用申請(意向書);核准=記錄+產開站指引文字,開站流程純手動(CR-0114 裁決 2)';
