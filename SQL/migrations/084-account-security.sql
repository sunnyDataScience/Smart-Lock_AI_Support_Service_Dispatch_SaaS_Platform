-- 084-account-security.sql
-- Phase I 帳號安全（A1 登入防爆破 / A3 改密碼撤 session）
--
-- A1：failed_login_attempts + locked_until —— 登入連續失敗鎖定。
-- A3：password_changed_at —— token iat 早於此時間者於驗證時失效（全域撤既有 session）。
-- A2（停權 token 即時失效）走既有 is_active 欄，不需新欄。
--
-- 慣例：ADD COLUMN IF NOT EXISTS、可重複套用。

ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN users.failed_login_attempts IS 'A1：連續登入失敗次數，達門檻設 locked_until，成功登入歸零';
COMMENT ON COLUMN users.locked_until IS 'A1：帳號鎖定到期時間（> now 即鎖定中，登入回 429 LOGIN_LOCKED）';
COMMENT ON COLUMN users.password_changed_at IS 'A3：最後一次改密碼/重設時間；token iat 早於此者驗證失效（全域撤 session）';
