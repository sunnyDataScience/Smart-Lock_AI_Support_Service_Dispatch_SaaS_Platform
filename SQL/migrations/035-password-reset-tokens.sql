-- 035-password-reset-tokens.sql
-- CR-0025 / ADR-0114：使用者自助忘記密碼 — 一次性 reset token。
-- 流程：request-password-reset 簽發高熵 token（只存雜湊）→ 寄 email →
--       confirm-password-reset 驗 token（未過期/未用）→ 改密碼 + 標 used + 撤 refresh。
--
-- 設計（見 ADR-0114）：
--   - token 明文絕不入庫：只存 SHA-256 token_hash（lookup 用雜湊比對）。
--   - TTL 30 分鐘、單次用：expires_at + used_at（NULL = 未用）。
--   - 帳號刪除連帶清 token：ON DELETE CASCADE。
--   - 全 idempotent（IF NOT EXISTS），可重複套用。

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL,                       -- SHA-256(raw token)；明文不入庫
    channel       TEXT NOT NULL DEFAULT 'email',       -- 送達管道（目前僅 email）
    expires_at    TIMESTAMP WITH TIME ZONE NOT NULL,   -- 簽發 + 30 分鐘
    used_at       TIMESTAMP WITH TIME ZONE,            -- NULL = 未用；confirm 後寫入
    requested_ip  INET,                                -- 防濫用稽核用
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- token_hash 唯一 + 查詢主鍵路徑
CREATE UNIQUE INDEX IF NOT EXISTS idx_prt_token_hash ON password_reset_tokens (token_hash);
-- 依 user 清理 / rate-limit 統計
CREATE INDEX IF NOT EXISTS idx_prt_user_id ON password_reset_tokens (user_id);
-- 過期清理掃描
CREATE INDEX IF NOT EXISTS idx_prt_expires_at ON password_reset_tokens (expires_at);
