-- ============================================================================
-- 028-invoices-payment-method.sql — invoices payment_method 欄位 + filter index
-- ============================================================================
-- 目的: 補 invoices 表 payment_method 欄位, 解 admin/accounting/invoices page
-- payment_method dropdown 從 disabled → enabled (filter by 付款方式).
--
-- 對齊 Phase 5-7 Enhancement Roadmap #9 (批次/多步審批) 旁支: invoice query
-- 支援 payment_method 欄位讓 admin 能依付款方式檢視 invoice list.
-- ============================================================================

BEGIN;

ALTER TABLE invoices
  ADD COLUMN IF NOT EXISTS payment_method text
    CHECK (payment_method IS NULL OR payment_method IN (
      'credit_card', 'bank_transfer', 'cash', 'line_pay', 'other'
    ));

COMMENT ON COLUMN invoices.payment_method IS
  'Payment method: credit_card/bank_transfer/cash/line_pay/other (NULL when unpaid)';

CREATE INDEX IF NOT EXISTS idx_invoices_payment_method
  ON invoices(payment_method)
  WHERE payment_method IS NOT NULL;

COMMIT;
