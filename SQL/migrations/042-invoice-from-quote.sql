-- 042-invoice-from-quote.sql
--
-- WHY（CR-0035 S5 / 20260617 gap-audit 雙領域盤點）：
--   技師撥款月結 CR-0012 已做；缺口在客戶側帳單 —— invoices 表只讀（無 create path），
--   報價 accepted（CR-0032）後無任何後續（無發票、無 outbox）。本 migration 為「報價→應收
--   發票」接線預留欄位：追溯來源報價 + mock 金額旗標（決議 5；稅率/訂金/拆帳待 esales Q-07/08）。
--
-- WHAT：
--   invoices 加 quote_id（追溯來源報價，nullable 向後相容 + 既有 work_order_id UNIQUE 仍為冪等鍵）
--   + is_mock（金額來自 esales mock 草稿時為 TRUE）。
--
-- 性質：DB schema（向後相容，全 IF NOT EXISTS 可重套）。mock-first，正式金額/稅率走 §8 裁決。

ALTER TABLE invoices ADD COLUMN IF NOT EXISTS quote_id UUID REFERENCES quote(id) ON DELETE SET NULL;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS is_mock BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_invoices_quote ON invoices(quote_id);

COMMENT ON COLUMN invoices.quote_id IS '來源報價（CR-0035；報價 accepted 自動開立應收發票時回填）';
COMMENT ON COLUMN invoices.is_mock IS '金額/稅率來自 esales mock 草稿（決議 5）；正式值待 esales Q-07/08 覆核轉 FALSE';
