-- Schema_line_notify.sql(技師權威庫 lock_tech)— CR-0169 師傅 LINE 推播
--
-- 平台 LINE 官方號綁定(業主 2026-07-17 裁決:HD-1=c 綁定碼先行、HD-3=b 指派必推
-- +池內新單可開關、HD-4=a line_user_id 明文 UI 遮蔽)。
-- 冪等可重跑。套用:docker exec -i lock-tech-tech-db-1 psql -U lock -d lock_tech < 本檔

-- 技師綁定欄位 + 池內新單推播開關
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS line_user_id VARCHAR(64);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS notify_pool_new BOOLEAN NOT NULL DEFAULT TRUE;
COMMENT ON COLUMN technicians.line_user_id IS 'CR-0169/CR-0173 平台 LINE 官方號綁定;CR-0173 起改存 line_user_id_enc,本欄過渡期保留 legacy 明文,回填後停用';
COMMENT ON COLUMN technicians.notify_pool_new IS 'CR-0169 搶單池新單 LINE 推播開關(HD-3=b,師傅自控費用/打擾)';

-- CR-0173(2026-07-20):line_user_id 欄位級加密(app 層 Fernet)+ blind index。
-- 推翻 HD-4=a 明文儲存(HD-G=有合規驅動,業主裁決)。app 讀寫走 core/line_uid_crypto.py:
--   line_user_id_enc  = Fernet 密文(非確定性);新綁定停寫明文 line_user_id(過渡期並存、回退讀)。
--   line_user_id_bidx = HMAC-SHA256 索引(確定性)供等值查(換綁去重;Fernet 密文無法等值比對)。
-- 既有明文列回填:scripts/backfill_tech_line_uid_encryption.py(app 層,SQL 無法跑 Fernet)。
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS line_user_id_enc  TEXT;
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS line_user_id_bidx CHAR(64);
COMMENT ON COLUMN technicians.line_user_id_enc  IS 'CR-0173 line_user_id Fernet 密文(推翻 HD-4=a)';
COMMENT ON COLUMN technicians.line_user_id_bidx IS 'CR-0173 line_user_id blind index HMAC-SHA256(等值查用)';
CREATE INDEX IF NOT EXISTS idx_technicians_line_bidx
    ON technicians (line_user_id_bidx) WHERE line_user_id_bidx IS NOT NULL;

-- 一次性綁定碼(6 位,TTL 10 分鐘,hash 存庫,單次使用)
CREATE TABLE IF NOT EXISTS technician_line_bind_codes (
    id            uuid DEFAULT uuid_generate_v4() NOT NULL,
    technician_id uuid NOT NULL,
    code_hash     text NOT NULL,
    expires_at    timestamp with time zone NOT NULL,
    used_at       timestamp with time zone,
    created_at    timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT technician_line_bind_codes_pkey PRIMARY KEY (id),
    CONSTRAINT technician_line_bind_codes_tech_fkey
        FOREIGN KEY (technician_id) REFERENCES technicians(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tlbc_code_hash ON technician_line_bind_codes (code_hash);
CREATE INDEX IF NOT EXISTS idx_tlbc_expires ON technician_line_bind_codes (expires_at);
