-- 099-quote-line-items-nullable-wo.sql
-- CR-0161：quote_line_items.work_order_id DROP NOT NULL（報價先行加品項 500 修復）
--
-- Root cause：037 建 quote_line_items 時為 work_order 層（CR-0027），work_order_id NOT NULL；
-- 041 升為 quote 層（加 quote_id）仍保留該欄相容；CR-0128「報價先行」允許
-- quote.work_order_id=NULL（開單後回填），但卡階段 add_line 寫入
-- quote_line_items.work_order_id=NULL → NotNullViolation 500（UAT 實測暴露）。
--
-- 修：放寬為 nullable。FK（REFERENCES work_orders ON DELETE CASCADE）保留——NULL 值
-- 免 FK 檢查、已綁定行仍受 cascade 保護。開單時 bind_quotes_to_work_order 補回填 lines，
-- 讓 work_order_document / technician_commission 等靠 work_order_id 關聯的讀取者維持正常。

ALTER TABLE quote_line_items ALTER COLUMN work_order_id DROP NOT NULL;

COMMENT ON COLUMN quote_line_items.work_order_id IS
  'CR-0161 nullable：報價先行（CR-0128）卡階段品項尚無工單，開單後由 bind_quotes_to_work_order 回填';
