-- migrate-targets: platform
-- ============================================================================
-- 121-service-principal-credentials.sql — S2S 身分與憑證生命週期
-- （CR-0190 / ADR-036）
-- ============================================================================
--
-- 明文 secret 只在建立/輪替回應出現一次；資料庫只保存 HMAC-SHA256 digest。
-- principal 持有 audience/scope/tenant grant，credential 只負責可撤銷、可輪替的
-- 驗證材料，避免把真人 users/JWT 與機器身分混用。
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_principals (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 VARCHAR(120) NOT NULL UNIQUE,
    description          VARCHAR(500),
    status               VARCHAR(20) NOT NULL DEFAULT 'active',
    audiences            TEXT[] NOT NULL,
    scopes               TEXT[] NOT NULL,
    allowed_tenant_ids   UUID[] NOT NULL DEFAULT '{}',
    allow_all_tenants    BOOLEAN NOT NULL DEFAULT FALSE,
    created_by           UUID NOT NULL REFERENCES users(id),
    created_action_id    UUID NOT NULL UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_service_principal_status
        CHECK (status IN ('active', 'suspended', 'retired')),
    CONSTRAINT chk_service_principal_audiences CHECK (cardinality(audiences) > 0),
    CONSTRAINT chk_service_principal_scopes CHECK (cardinality(scopes) > 0),
    CONSTRAINT chk_service_principal_tenant_grant
        CHECK (allow_all_tenants OR cardinality(allowed_tenant_ids) > 0)
);

CREATE TABLE IF NOT EXISTS service_credentials (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    principal_id         UUID NOT NULL REFERENCES service_principals(id) ON DELETE CASCADE,
    credential_prefix    VARCHAR(32) NOT NULL UNIQUE,
    secret_hash          CHAR(64) NOT NULL,
    hash_version         SMALLINT NOT NULL DEFAULT 1,
    expires_at           TIMESTAMPTZ NOT NULL,
    revoked_at           TIMESTAMPTZ,
    revoked_reason       VARCHAR(300),
    rotated_from_id      UUID REFERENCES service_credentials(id),
    created_by           UUID NOT NULL REFERENCES users(id),
    last_used_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_action_id       UUID NOT NULL,
    CONSTRAINT chk_service_credential_expiry
        CHECK (expires_at > created_at),
    CONSTRAINT chk_service_credential_hash
        CHECK (secret_hash ~ '^[0-9a-f]{64}$')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_service_credential_action
    ON service_credentials (principal_id, last_action_id);
CREATE INDEX IF NOT EXISTS idx_service_credentials_active
    ON service_credentials (principal_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS service_auth_audit (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    principal_id         UUID REFERENCES service_principals(id),
    credential_id        UUID REFERENCES service_credentials(id),
    credential_prefix    VARCHAR(32),
    event_type           VARCHAR(40) NOT NULL,
    outcome              VARCHAR(20) NOT NULL,
    request_id           VARCHAR(100),
    audience             VARCHAR(120),
    required_scope       VARCHAR(120),
    tenant_id            UUID,
    detail_json          JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_service_auth_audit_outcome
        CHECK (outcome IN ('success', 'denied', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_service_auth_audit_principal_time
    ON service_auth_audit (principal_id, occurred_at DESC);

COMMENT ON COLUMN service_credentials.secret_hash IS
'SERVICE_CREDENTIAL_PEPPER keyed HMAC-SHA256；不得保存或 log 明文 secret。';
COMMENT ON COLUMN service_credentials.last_action_id IS
'建立/輪替的 Idempotency-Key；同 principal 重送不得生成第二把憑證。';
COMMENT ON COLUMN service_principals.created_action_id IS
'建立 principal 的 Idempotency-Key；遺失一次性 secret 後重送回 409，不重建 principal/credential。';
