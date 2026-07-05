-- ═══════════════════════════════════════════════════════════════════════════
-- 089-technician-kyc.sql — 師傅註冊擴充為 KYC 等級(CR-0115)
--
-- 業主裁決(CR-0115 §8):現有 6 欄註冊擴為三層 —— Tier 1 非敏感、Tier 2 敏感
-- PII、Tier 3 文件上傳。本 migration 落 Tier 1 欄位 + Tier 2 敏感 PII 獨立表。
-- (Tier 3 文件上傳的 registration_document + 兩階段 token 表於後續 migration。)
--
-- 設計依據:
--   §8-1 敏感 PII(身分證/銀行帳戶)存**獨立 technician_kyc 表** + 欄位加密
--        (app 層 Fernet,見 core/pii_crypto.py) + 讀取遮罩、不鏡射品牌庫。
--        → national_id / bank_account 只存密文欄(*_enc) + 末碼欄(*_last*)供遮罩
--          顯示;birth_date/address/bank_code/tax_id 敏感度較低,存明文於隔離表。
--   §8-4 最小必填 → 欄位全 nullable(必填在新表單層強制,後端加性非破壞)。
--
-- 慣例:IF NOT EXISTS / ADD COLUMN IF NOT EXISTS,可重複套用。
-- 落庫:師傅身分權威庫(tech-db,lock_tech);fallback 單庫時即主庫。
-- ═══════════════════════════════════════════════════════════════════════════

-- ── Tier 1 非敏感欄位(直接掛 technicians)──────────────────────────────────
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS years_experience       INTEGER;
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS bio                    TEXT;
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS vehicle_type           VARCHAR(20);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS availability_note      VARCHAR(40);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS emergency_contact_name  VARCHAR(100);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS emergency_contact_phone VARCHAR(50);
-- 服務條款/隱私權/背景查核授權同意時間(未同意不予註冊,由表單層強制)
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS terms_accepted_at      TIMESTAMPTZ;

-- ── Tier 2 敏感 PII 獨立表(§8-1)──────────────────────────────────────────
--  一師傅一列(technician_id UNIQUE);敏感值加密後存 *_enc,顯示末碼存 *_last*。
CREATE TABLE IF NOT EXISTS technician_kyc (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technician_id     UUID NOT NULL UNIQUE REFERENCES technicians(id) ON DELETE CASCADE,
    tenant_id         UUID NOT NULL,
    -- 身分證字號:密文 + 末 3 碼(遮罩顯示用)
    national_id_enc   TEXT,
    national_id_last3 VARCHAR(3),
    -- 撥款銀行帳戶:銀行代碼(較不敏感,明文)+ 帳號密文 + 末 4 碼
    bank_code         VARCHAR(10),
    bank_account_enc  TEXT,
    bank_account_last4 VARCHAR(4),
    -- 敏感度較低,存明文於隔離表
    birth_date        DATE,
    address           TEXT,
    tax_id            VARCHAR(8),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_technician_kyc_tenant ON technician_kyc (tenant_id);
