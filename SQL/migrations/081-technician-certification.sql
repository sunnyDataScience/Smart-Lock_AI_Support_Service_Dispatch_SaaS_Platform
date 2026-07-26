-- 081-technician-certification.sql
-- migrate-targets: brand,tech  (LOCK-62：技師表在品牌庫與技師庫皆存在，兩庫皆須套用)
-- WHY（CR-0104 / 師傅詳情頁假資料轉真 / 業主裁決「認證矩陣=建完整認證模組」）：
--   詳情頁「技能認證矩陣」5 列全寫死於前端（認證項目/品牌/取得日/到期日/狀態），與真實技師無關。
--   既有 technician_brand_authorization（063）為「品牌授權」（dispatch 媒合過濾用，UNIQUE(tech,brand)
--   一品牌一列、無認證項目名稱、無取得日期），無法承載「具名認證項目 + 取得/到期日」的結構化矩陣。
-- WHAT：新建 technician_certification（與 brand_authorization 職責分離）—— 一技師可多筆具名認證，
--   含 cert_name（認證項目）/ brand（關聯品牌，可空）/ obtained_at（取得日）/ expires_at（到期日，
--   NULL=無期限）。狀態（有效/即將到期/已過期）由 service 依 expires_at vs CURRENT_DATE computed，
--   不落欄。is_mock DEFAULT FALSE —— 此模組資料為 admin 後台真實登錄，非 seed 示意，故不預設 mock、不 seed。
--   純 CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS，idempotent 可重套。

CREATE TABLE IF NOT EXISTS technician_certification (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    technician_id   UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    cert_name       VARCHAR(120) NOT NULL,          -- 認證項目（如「電子鎖安裝認證」）
    brand           VARCHAR(100),                   -- 關聯品牌（可空）
    obtained_at     DATE,                           -- 取得日期（可空）
    expires_at      DATE,                           -- 到期日期（NULL=無期限）
    is_mock         BOOLEAN NOT NULL DEFAULT FALSE, -- 後台真實登錄，預設非 mock
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tech_cert_tech ON technician_certification(technician_id);
CREATE INDEX IF NOT EXISTS idx_tech_cert_tenant ON technician_certification(tenant_id);
