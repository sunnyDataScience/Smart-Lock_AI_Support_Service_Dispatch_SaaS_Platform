-- 036-workorder-standard-fields.sql
--
-- WHY（CR-0026 / 2026-06-17 會議 Action #1）：
--   會議當場點 UI 發現公單欄位對不上 Johnson 紙本工單 + esales 成本架。現行
--   work_orders 是扁平最小結構（只有 customer_name/phone/address + 兩個 FLOAT 價格），
--   缺設備辨識、服務類別、保固、完工細狀態、狀態原因、返修連回、對外金額。
--   決議 3：schema 先補欄位、前端才有資料可顯示。
--
-- WHAT：
--   work_orders 補欄位（全 nullable、可逆、向後相容）；補 tenant_id（work_orders /
--   scope_changes 皆無此欄，租戶隔離原靠 users join；本次補欄位 + backfill 既有列為
--   單租戶值，為 multi-tenant CR-0031 預留，並讓 outbox resolver 未來可直接用 wo.tenant_id）。
--   欄位語意參考來源（不可信，僅引語意）：docs/_source/01-workorder-erp.md #m05/#m08 +
--   派工單分析 PDF 6 模組。數值/列舉值由 app 層驗證，DB 不加 CHECK 以保彈性。
--
-- 影響：純 ADD COLUMN（不改既有欄、不刪資料），idempotent 可重跑。結構化成本拆項屬
--   CR-0027（quote_line_items），本 migration 只在 work_orders 留單一 customer_final_amount。

-- 1. work_orders 設備辨識（派工/材料判斷依據；brand/model 建單時從 problem_cards 複製）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS brand            VARCHAR(100);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS model            VARCHAR(100);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS serial_number    VARCHAR(100);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS door_type        VARCHAR(50);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS door_thickness   VARCHAR(50);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS is_interior_door BOOLEAN;

-- 2. 服務類別 + 問題類型（service_category：install/warranty_in/warranty_out/repair；app 驗證）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS service_category VARCHAR(30);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS problem_type     VARCHAR(100);

-- 3. 保固（serial_number 綁保固；warranty_status：in_warranty/out_warranty/not_applicable，本輪人工填）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS warranty_status  VARCHAR(30);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS purchase_date    DATE;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS invoice_no       VARCHAR(100);

-- 4. 完工細狀態（M05 Q052 六段，補在粗 status 之下；app 驗證）
--    pending_report / pending_photos / pending_customer_confirm / pending_cs_review / completed / closed
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS completion_status VARCHAR(40);

-- 5. 狀態原因（BR-M05-01：cancel/reopen/reschedule/refund/dispute 必填；現行 reason 只塞 service_report 字串）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS status_reason    TEXT;

-- 6. 返修連回原工單（BR-M05-02：reopen 不覆蓋歷史）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS parent_work_order_id UUID;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_work_orders_parent'
    ) THEN
        ALTER TABLE work_orders
            ADD CONSTRAINT fk_work_orders_parent
            FOREIGN KEY (parent_work_order_id) REFERENCES work_orders(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 7. 對外單一金額（客戶端電子工單只露此值；成本拆項在 CR-0027 quote_line_items）
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS customer_final_amount NUMERIC(12,2);

-- 8. tenant_id（multi-tenant 預留；backfill 既有列走 users join 鏈推導）
ALTER TABLE work_orders  ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE scope_changes ADD COLUMN IF NOT EXISTS tenant_id UUID;

UPDATE work_orders wo
SET tenant_id = u.tenant_id
FROM problem_cards pc, conversations c, users u
WHERE wo.problem_card_id = pc.id
  AND pc.conversation_id = c.id
  AND c.user_id = u.id
  AND wo.tenant_id IS NULL;

UPDATE scope_changes sc
SET tenant_id = u.tenant_id
FROM work_orders wo, problem_cards pc, conversations c, users u
WHERE sc.work_order_id = wo.id
  AND wo.problem_card_id = pc.id
  AND pc.conversation_id = c.id
  AND c.user_id = u.id
  AND sc.tenant_id IS NULL;

-- 9. indexes
CREATE INDEX IF NOT EXISTS idx_work_orders_parent     ON work_orders (parent_work_order_id) WHERE parent_work_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_work_orders_tenant     ON work_orders (tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scope_changes_tenant   ON scope_changes (tenant_id) WHERE tenant_id IS NOT NULL;

COMMENT ON COLUMN work_orders.service_category      IS 'install/warranty_in/warranty_out/repair（安裝/保內/保外/維修）— app 層驗證';
COMMENT ON COLUMN work_orders.completion_status     IS 'M05 Q052 六段完工細狀態 — app 層驗證；粗狀態仍用 status';
COMMENT ON COLUMN work_orders.status_reason         IS 'BR-M05-01：cancel/reopen/reschedule 等狀態變更必填原因';
COMMENT ON COLUMN work_orders.parent_work_order_id  IS 'BR-M05-02：返修/reopen 連回原工單，不覆蓋歷史';
COMMENT ON COLUMN work_orders.customer_final_amount IS '對外單一最終金額（客戶端電子工單只露此值）；成本拆項見 CR-0027 quote_line_items';
COMMENT ON COLUMN work_orders.tenant_id            IS 'multi-tenant 預留（CR-0031）；既有列 backfill 自 users join；目前仍 single-tenant';
