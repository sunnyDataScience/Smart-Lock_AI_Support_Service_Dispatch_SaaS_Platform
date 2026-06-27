-- 083-technician-penalty-bonus-ledger.sql
-- WHY（CR-0107 / 業主裁決 2026-06-27）：師傅詳情頁右欄「獎懲紀錄」前端寫死 4 筆假資料
--   （高評價獎金/準時完工/遲到扣款/客戶推薦），來源完全無此規則。源頭查證：
--   ① ERP spec Q121 明令「師傅扣款…不能交給 AI 或工程師自行假設」→ 獎金/扣款規則不可腦補自動算；
--   ② 唯一規則明確者為「取消失約扣款」（BR-CANCEL-007：同月首次免責 / ≥2 次扣 NTD500 + weight-10 /
--      不可抗力免責），已存於 public.cancellation.technician_penalty 欄。
--   業主裁決「後台手動登錄 + 自動帶取消罰」：建逐筆 ledger 供 admin 主管登錄實際獎懲事件（符合 Q121
--   主管拍板），list 時再 UNION 既有取消失約扣款（read-only 自動帶入）。
-- WHAT：新表 saas.technician_penalty_bonus_ledger（手動逐筆）。自動帶入的取消罰不落此表（讀 cancellation）。
--   amount 一律正值；entry_type 決定加減顯示。idempotent。

CREATE TABLE IF NOT EXISTS saas.technician_penalty_bonus_ledger (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id            UUID NOT NULL,
    technician_id        UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    entry_type           VARCHAR(10) NOT NULL CHECK (entry_type IN ('bonus', 'penalty')),
    title                VARCHAR(120) NOT NULL,       -- 事由（如「高評價獎金」「遲到扣款」）
    reason               TEXT,                        -- 詳細說明（選填）
    amount               NUMERIC(12,2) NOT NULL CHECK (amount >= 0),  -- 正值；entry_type 決定加減
    occurred_date        DATE NOT NULL,               -- 事件發生日
    source_work_order_id UUID,                        -- 關聯工單（選填）
    created_by           UUID,                        -- 登錄主管（actor）
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tech_pb_ledger_tech ON saas.technician_penalty_bonus_ledger(technician_id);
CREATE INDEX IF NOT EXISTS idx_tech_pb_ledger_tenant ON saas.technician_penalty_bonus_ledger(tenant_id);
