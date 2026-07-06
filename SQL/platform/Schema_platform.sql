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

-- 業界補充欄位(申請導入表單移到 platform 站 /platform/apply 時擴充;全選填、additive)
-- ADD COLUMN IF NOT EXISTS → fresh install（CREATE 已建表則跳過）與既有 DB 皆可重跑。
ALTER TABLE brand_applications ADD COLUMN IF NOT EXISTS website                  VARCHAR(255); -- 公司網站
ALTER TABLE brand_applications ADD COLUMN IF NOT EXISTS coverage_regions         TEXT;         -- 服務涵蓋地區(派工媒合用)
ALTER TABLE brand_applications ADD COLUMN IF NOT EXISTS store_count              INTEGER;      -- 門市/據點數
ALTER TABLE brand_applications ADD COLUMN IF NOT EXISTS expected_monthly_orders  VARCHAR(30);  -- 預估月工單量級距
ALTER TABLE brand_applications ADD COLUMN IF NOT EXISTS main_brands              TEXT;         -- 主營品牌/產品
ALTER TABLE brand_applications ADD COLUMN IF NOT EXISTS referral_source          VARCHAR(50);  -- 如何得知平台(行銷歸因)

-- 同一 email 同時只能有一件待審申請(核准/拒絕後可再申請)
CREATE UNIQUE INDEX IF NOT EXISTS uq_brand_app_pending_email
    ON brand_applications(email) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_brand_app_status_created
    ON brand_applications(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_brand_app_ip_created
    ON brand_applications(submitted_ip, created_at DESC);

COMMENT ON TABLE brand_applications IS '品牌廠商鎖店平台使用申請(意向書);核准=記錄+產開站指引文字,開站流程純手動(CR-0114 裁決 2)';

-- ─────────────────────────────────────────────────────────────────────────────
-- [4] monitor_target — 維運監控目標 registry(CR-0116)
--     「一品牌一 GCP 專案」部署下,用 GCP Console 一家一家看 container 狀態不可行
--     (>10 視窗上限)。此表登記各品牌服務的 health URL,platform console「維運監控」
--     分頁前端輪詢 → 後端並發探測 → 一頁紅綠燈。定位=非技術者一眼看的即時狀態;
--     深度指標/告警/歷史走 GCP 原生(Metrics Scope + Uptime Check + Alerting),
--     故此表**不存狀態歷史**(CR-0116 §8-Q3 裁決 a:MVP 即時紅綠燈)。
--     粒度=一目標一列(§8-Q1 裁決 b:brand+label 分組,agent/api/web 各一列)。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS monitor_target (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand       VARCHAR(80)  NOT NULL,               -- 分組標籤(品牌 key,如 locksmart)
    label       VARCHAR(80)  NOT NULL,               -- 服務標籤(派工 API / Agent / 師傅 API)
    url         VARCHAR(500) NOT NULL,               -- 完整 health URL(含 path;§8-Q5 裁決 a)
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    sort_order  INTEGER      NOT NULL DEFAULT 0,
    note        VARCHAR(255),                        -- 選填備註
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_monitor_target_order
    ON monitor_target(brand, sort_order, label);

COMMENT ON TABLE monitor_target IS '維運監控目標 registry(CR-0116);一目標一列 health URL,console 即時探測紅綠燈,不存歷史(告警走 GCP)';
