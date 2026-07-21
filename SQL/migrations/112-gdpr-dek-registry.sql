-- ═══════════════════════════════════════════════════════════════════════════
-- 112-gdpr-dek-registry.sql — GDPR crypto-shredding：per-subject DEK 註冊表（CR-0176）
--
-- WHY：
--   FR-API-16 / NFR-Priv-008 要求 forget 的 T0「銷毀金鑰 → 資料即刻不可復原」
--   (crypto-shredding)。現況 gdpr_forget_service.soft_delete 是明文覆寫，無任何 DEK；
--   pii_crypto / line_uid_crypto 又是單一 master key（銷毀＝全部人不可讀，無法只 shred
--   一個 data subject）。→ 引入 envelope 加密：KEK wrap 每個 subject 一把 DEK，forget
--   時銷毀該 subject 的 DEK（tombstone），其 PII 密文瞬間不可解且不影響他人。
--
-- WHAT：
--   1. saas.data_encryption_key — per-subject DEK registry（wrapped_dek 由 KEK 加密）。
--      status active→destroyed；destroyed 時 wrapped_dek 清空 + destroyed_at 蓋章
--      (HD-4 tombstone，row 保留供稽核)；partial unique index 保證至多一把 active/subject。
--   2. users 加 display_name_enc / email_enc / phone_enc（密文欄，S2 dual-write 用；
--      本增量僅備妥 schema，全站讀寫 cutover 與存量 backfill 為後續 S2/S3）。
--
-- IMPACT：
--   純新增（表 + nullable 欄），零回歸。ADR-020 三庫：本 migration 為品牌庫；
--   技師權威庫 / 平台庫 users 的同款覆蓋為後續增量。
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS saas.data_encryption_key (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_user_id  UUID NOT NULL,
    tenant_id        UUID,
    wrapped_dek      TEXT,                       -- KEK 加密後的 DEK 材料；destroyed 後為 NULL
    key_version      INTEGER NOT NULL DEFAULT 1,
    status           VARCHAR(20) NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'destroyed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    destroyed_at     TIMESTAMPTZ,
    destroyed_by     UUID,
    -- tombstone 不變式：destroyed 必有時間戳且金鑰材料已清空；active 必有 wrapped
    CONSTRAINT dek_status_consistent CHECK (
        (status = 'active'    AND wrapped_dek IS NOT NULL AND destroyed_at IS NULL) OR
        (status = 'destroyed' AND wrapped_dek IS NULL     AND destroyed_at IS NOT NULL)
    )
);

-- 至多一把 active DEK / subject（支援 dek_service._store_wrapped 的 ON CONFLICT）
CREATE UNIQUE INDEX IF NOT EXISTS uq_dek_active_per_subject
    ON saas.data_encryption_key (subject_user_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_dek_subject
    ON saas.data_encryption_key (subject_user_id);

COMMENT ON TABLE saas.data_encryption_key IS
    'CR-0176 per-subject DEK registry；forget 時 status→destroyed 清 wrapped_dek＝crypto-shred';

-- users PII 密文欄（S2 dual-write 用；本增量僅備妥 schema）
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name_enc TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_enc        TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_enc        TEXT;
