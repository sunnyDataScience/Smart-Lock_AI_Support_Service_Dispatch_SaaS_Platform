-- 039-dispatch-mode.sql
--
-- WHY（CR-0030 / 2026-06-17 會議 Action #7）：
--   會議拍板派工模式切換三檔——租戶手動派 / 平台代派(付費點) / 自動媒合。本輪做前兩檔
--   (自動媒合留 Report 2)。現行 assign_order 無條件直接派工,無 tenant 層派工模式設定,
--   平台代派的「付費」事件也無法記帳追蹤。
--
-- WHAT：
--   (1) saas.tenant.dispatch_mode：租戶層派工模式設定(manual/platform_paid/auto_match;
--       app 驗證列舉),預設 manual。
--   (2) work_orders.dispatched_via：記錄該工單實際走哪檔派工(manual/platform/auto_match),
--       平台代派(platform)= 可計費事件,供日後計費對帳(計費規則待業主,本輪只標記)。
--
-- 影響：純 ADD COLUMN(nullable/有預設),idempotent。

ALTER TABLE saas.tenant  ADD COLUMN IF NOT EXISTS dispatch_mode  VARCHAR(20) NOT NULL DEFAULT 'manual';
ALTER TABLE work_orders  ADD COLUMN IF NOT EXISTS dispatched_via VARCHAR(20);

COMMENT ON COLUMN saas.tenant.dispatch_mode    IS 'CR-0030 租戶派工模式:manual(租戶手動派)/platform_paid(平台代派,付費點)/auto_match(自動媒合,Report 2)。app 驗證';
COMMENT ON COLUMN work_orders.dispatched_via   IS 'CR-0030 該工單實際派工來源:manual/platform/auto_match;platform=可計費事件(計費規則待業主)';
