-- ═══════════════════════════════════════════════════════════════════════════
-- 114-user-pii-blind-index.sql — users email/phone blind index 欄（CR-0176 S5 前置，業主 0722 A1）
--
-- WHY：S5 要 DROP email/phone 明文，但 login／EMAIL_TAKEN 去重／phone 去重是
--      WHERE 等值查——Fernet 密文非確定性查不了。比照 CR-0173（technician
--      line_user_id_bidx）前例補 HMAC 盲索引欄。
-- WHAT：
--   1. users 加 email_bidx / phone_bidx TEXT（HMAC-SHA256 hex，金鑰 env
--      USER_PII_BIDX_KEY，計算在 app 層 core/user_pii_bidx.py）
--   2. partial index 供等值查（NULL 不佔索引——backfill 前舊列/技師投影列皆 NULL）
-- IMPACT：純加欄零回歸；查詢端已改雙謂詞（明文 OR bidx），本 migration 未套前
--         舊查詢仍走明文、套後新列即用 bidx。backfill＝scripts/
--         backfill_user_pii_encryption.py（同輪擴充）。
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_bidx TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_bidx TEXT;

CREATE INDEX IF NOT EXISTS idx_users_email_bidx
    ON users (email_bidx) WHERE email_bidx IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_phone_bidx
    ON users (phone_bidx) WHERE phone_bidx IS NOT NULL;

COMMENT ON COLUMN users.email_bidx IS
    'CR-0176 S5 前置：email HMAC 盲索引（等值查用；金鑰 USER_PII_BIDX_KEY）';
COMMENT ON COLUMN users.phone_bidx IS
    'CR-0176 S5 前置：phone HMAC 盲索引（等值查用；金鑰 USER_PII_BIDX_KEY）';
