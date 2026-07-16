-- Schema_password_reset.sql（技師權威庫 lock_tech）— 16.5.4-fix / 業主 2026-07-16 拍板
--
-- 技師忘記密碼的 reset token 表:CR-0112 拆庫後技師 user 在權威庫,且品牌投影
-- 不含技師 email/password_hash(tech_mirror 白名單)→ 品牌庫的 reset 流程對技師
-- 永遠「查無帳號」。surface 分流(API_SURFACE=tech → 本庫)後,token 與 users
-- 同庫,FK 參照完整性得以保留(品牌庫同名表的 FK 存不了本庫 user_id)。
--
-- 結構同品牌庫 password_reset_tokens(pg_dump 對照,2026-07-16);冪等可重跑。
-- 套用:docker exec -i lock-tech-tech-db-1 psql -U lock -d lock_tech < 本檔
-- (新開站/重拆技師庫時隨 tech_authority/*.sql 一起套)

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id           uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id      uuid NOT NULL,
    token_hash   text NOT NULL,
    channel      text DEFAULT 'email'::text NOT NULL,
    expires_at   timestamp with time zone NOT NULL,
    used_at      timestamp with time zone,
    requested_ip inet,
    created_at   timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id),
    CONSTRAINT password_reset_tokens_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prt_expires_at ON password_reset_tokens (expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_prt_token_hash ON password_reset_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_prt_user_id ON password_reset_tokens (user_id);
