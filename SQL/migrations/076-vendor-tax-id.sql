-- 076-vendor-tax-id.sql
-- WHY（CR-0089）：廠商（發案者：品牌商/鎖店/經銷商）註冊缺台灣 B2B 關鍵欄位
--   「統一編號」，平台無法對廠商開立發票/對帳/簽約。業主逐頁測試時裁決：加統編
--   + 公司名改必填。
-- WHAT：vendors +tax_id（統一編號，8 碼數字）。既有列允許 NULL（向後相容，不回溯
--   既有資料）；新註冊由 API（VendorRegisterBody pattern ^\d{8}$）+ 前端強制必填。
--   純 ADD COLUMN IF NOT EXISTS，可重複套用（idempotent）。
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS tax_id VARCHAR(8);
COMMENT ON COLUMN vendors.tax_id IS
  'CR-0089：廠商統一編號（台灣 B2B 開發票/對帳/簽約）；既有列可 NULL，新註冊 API 強制必填 8 碼';
