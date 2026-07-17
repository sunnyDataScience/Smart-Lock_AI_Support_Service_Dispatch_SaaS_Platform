-- Schema_line_notify.sql(技師權威庫 lock_tech)— CR-0169 師傅 LINE 推播
--
-- 平台 LINE 官方號綁定(業主 2026-07-17 裁決:HD-1=c 綁定碼先行、HD-3=b 指派必推
-- +池內新單可開關、HD-4=a line_user_id 明文 UI 遮蔽)。
-- 冪等可重跑。套用:docker exec -i lock-tech-tech-db-1 psql -U lock -d lock_tech < 本檔

-- 技師綁定欄位 + 池內新單推播開關
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS line_user_id VARCHAR(64);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS notify_pool_new BOOLEAN NOT NULL DEFAULT TRUE;
COMMENT ON COLUMN technicians.line_user_id IS 'CR-0169 平台 LINE 官方號綁定(U 開頭 userId;明文存、UI 遮蔽)';
COMMENT ON COLUMN technicians.notify_pool_new IS 'CR-0169 搶單池新單 LINE 推播開關(HD-3=b,師傅自控費用/打擾)';

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
