-- 037-quote-line-items.sql
--
-- WHY（CR-0027 / 2026-06-17 會議決議 4）：
--   會議「報價成本明細沒做（成本架資料庫沒建）」。決議 4：後台看成本明細（每品項
--   單價/材料/內部估價），客戶端電子工單只露最終價。決議 5：報價數字當 mock（打 8 成）。
--   現行只有 work_orders.estimated_price/final_price 兩個裸 FLOAT + invoices.line_items
--   (JSONB 無結構)，無法做欄位級 RBAC 成本遮蔽，也無結構化拆項。
--
-- WHAT：
--   新建 quote_line_items（work_order 層成本拆項）。unit_price=內部成本「僅後台可讀」，
--   customer_price=對外金額。is_mock 預設 TRUE（對應決議 5 打 8 成、待財務覆核）。
--   對外總額落到 work_orders.customer_final_amount（migration 036 已建）。
--   不建 service_catalog/material_catalog（屬 CR-0027 完整版/Phase II）；數值由 app seed，
--   嚴禁直接抄 esales xlsx 原值（sourcing rule）。
--
-- 影響：純新增表，idempotent。tenant_id 預留（multi-tenant CR-0031）。

CREATE TABLE IF NOT EXISTS quote_line_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id   UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id       UUID,                              -- multi-tenant 預留（CR-0031）
    item_name       VARCHAR(120) NOT NULL,
    category        VARCHAR(20) NOT NULL DEFAULT 'other',  -- labor/material/other（app 驗證）
    unit_price      NUMERIC(12,2) NOT NULL DEFAULT 0,   -- 內部成本（僅後台可讀，server 端 RBAC 遮蔽）
    quantity        INTEGER NOT NULL DEFAULT 1,
    customer_price  NUMERIC(12,2) NOT NULL DEFAULT 0,   -- 對外金額（客戶端電子工單可見）
    is_mock         BOOLEAN NOT NULL DEFAULT TRUE,      -- 決議 5：打 8 成 mock、待財務覆核
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_quote_line_qty_pos CHECK (quantity >= 1)
);

CREATE INDEX IF NOT EXISTS idx_quote_line_items_wo
    ON quote_line_items (work_order_id);
CREATE INDEX IF NOT EXISTS idx_quote_line_items_tenant
    ON quote_line_items (tenant_id) WHERE tenant_id IS NOT NULL;

COMMENT ON TABLE  quote_line_items IS 'CR-0027 公單成本拆項：unit_price 內部成本僅後台可讀、customer_price 對外；is_mock 待財務覆核';
COMMENT ON COLUMN quote_line_items.unit_price IS '內部成本（僅 admin/operations_manager 可讀；客戶端電子工單絕不含）';
COMMENT ON COLUMN quote_line_items.customer_price IS '對外金額（客戶端電子工單只露此值與其加總）';
COMMENT ON COLUMN quote_line_items.is_mock IS '決議 5：報價 mock（打 8 成），匯入 production 前須財務覆核';
