-- Schema_cqrs_projection.sql（技師權威庫 lock_tech）— CR-0166 R4 / ADR-017
--
-- 技師平台 CQRS 讀模型：訂閱各品牌 workorder.lifecycle / commission.accrued 事件，
-- 維護「技師視角」跨品牌投影，供師傅 web 讀。欄位最小化（隱私/最小權限，ADR-017 §投影隱私）：
-- 只存投影所需摘要＋租戶標記，不整包複製品牌敏感資料。
--
-- 由 event_consumer 於啟動時 CREATE TABLE IF NOT EXISTS 確保（opt-in，KAFKA_BOOTSTRAP 設才跑）。

-- 工單投影（技師視角，跨品牌）
CREATE TABLE IF NOT EXISTS technician_workorder_projection (
    work_order_id     UUID PRIMARY KEY,
    tenant_id         UUID NOT NULL,                 -- 租戶標記（防跨租戶外洩）
    technician_id     UUID,                          -- 該工單指派技師（NULL=未派/已退）
    status            VARCHAR(30),
    document_number   VARCHAR(50),
    district          VARCHAR(100),                  -- 地區（非完整地址，最小揭露）
    scheduled_time    VARCHAR(50),
    last_event_type   VARCHAR(50),
    occurred_at       TIMESTAMP WITH TIME ZONE,
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tech_wo_proj_tech
    ON technician_workorder_projection (technician_id, status);

-- 佣金投影（技師跨品牌 accrued 明細，供 statement 彙總）
CREATE TABLE IF NOT EXISTS technician_commission_projection (
    settlement_id     UUID PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    reconciliation_id UUID,
    technician_id     UUID NOT NULL,
    amount            NUMERIC(12,2) NOT NULL,
    currency          VARCHAR(8) NOT NULL DEFAULT 'TWD',
    accrued_at        TIMESTAMP WITH TIME ZONE,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tech_comm_proj_tech
    ON technician_commission_projection (technician_id, accrued_at DESC);

-- 事件去重（event_id 冪等，跨重啟安全）
CREATE TABLE IF NOT EXISTS event_consumer_dedup (
    event_id      TEXT PRIMARY KEY,
    topic         VARCHAR(64) NOT NULL,
    processed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
