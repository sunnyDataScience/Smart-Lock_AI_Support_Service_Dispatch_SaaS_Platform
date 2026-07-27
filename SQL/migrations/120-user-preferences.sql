-- migrate-targets: brand,tech,platform
-- ============================================================================
-- 120-user-preferences.sql — 三庫各自權威的跨裝置偏好（CR-0190 / ADR-034）
-- ============================================================================
--
-- 同一份結構分流至三庫，但資料 owner 不跨庫：
--   brand    scope_tenant_id = JWT / path tenant
--   tech     scope_tenant_id = 全零 UUID（技師本人跨品牌偏好）
--   platform scope_tenant_id = 全零 UUID（平台治理偏好）
--
-- value_json 不是任意設定垃圾桶：API 有 portal×key allowlist 與形狀驗證，DB 再以
-- 16 KiB 上限防止繞過 API 的無界 payload。version 提供 CAS；last_action_id 讓同一次
-- user action retry 回放既有結果而不多加版本。
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_preferences (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    principal_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope_tenant_id   UUID NOT NULL,
    portal            VARCHAR(20) NOT NULL,
    preference_key    VARCHAR(80) NOT NULL,
    value_json        JSONB NOT NULL,
    version           INTEGER NOT NULL DEFAULT 1,
    last_action_id    UUID NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_preferences_portal
        CHECK (portal IN ('brand', 'tech', 'platform')),
    CONSTRAINT chk_user_preferences_version CHECK (version >= 1),
    CONSTRAINT chk_user_preferences_value_size
        CHECK (octet_length(value_json::text) <= 16384),
    CONSTRAINT uq_user_preferences_scope
        UNIQUE (principal_id, scope_tenant_id, portal, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_principal
    ON user_preferences (principal_id, scope_tenant_id, portal, updated_at DESC);

COMMENT ON TABLE user_preferences IS
'CR-0190/ADR-034：跨裝置偏好；三庫各自持有其 principal 的權威資料，不建立第四份 user DB。';
COMMENT ON COLUMN user_preferences.last_action_id IS
'同一次使用者 action 的穩定冪等鍵；retry 不增加 version。';
