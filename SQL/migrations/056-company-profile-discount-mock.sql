-- 056-company-profile-discount-mock.sql
--
-- WHY（CR-0046 / esales Q-11 + Q-12）：翻遍 20260617 資料夾後，Q-11（客服優惠權限幅度）與
--   Q-12（公司抬頭/客服電話/保固+取消+追加價條款文字）資料夾確實沒有，屬公司專屬。業主指示
--   「先生成假資料，確認後再替換」（同會議決議 5 mock 模式）。值入 M18 config → 業主可動態替換、
--   不需改 code。所有值標 is_mock + source「範例待業主確認」，文字內含「（範例…）」便於辨識。
--
-- WHAT：兩 namespace + 全域 active default（idempotent）：
--   - company_profile：Q-12 公司抬頭/電話 + 保固/取消費/追加價三段條款文字（電子工單 PDF 渲染）。
--   - discount_policy：Q-11 報價核准門檻 + 客服折扣權限（quote 送審 gate）。

-- 1. company_profile（Q-12）— 客戶電子工單/報價單文案
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('company_profile',
   '公司報價單/電子工單文案（CR-0046 / esales Q-12；範例待業主確認）',
   '{"type":"object","properties":{"company_name":{"type":"string"},"customer_service_phone":{"type":"string"},"warranty_text":{"type":"string"},"cancellation_clause":{"type":"string"},"surcharge_clause":{"type":"string"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'company_profile', 'default',
  jsonb_build_object(
    'company_name', 'Chairlock 智慧鎖到府服務（範例待業主確認）',
    'customer_service_phone', '0800-000-000（範例待替換）',
    'warranty_text', '本店購買並安裝之電子鎖，享原廠保固及本店安裝保固 12 個月；客戶自備鎖之代工安裝，僅保固安裝品質，產品本身故障不在保固範圍。（範例條款，待業主／法務確認）',
    'cancellation_clause', '派工後取消依階段收取取消費：師傅已出發 300 元、已排定時段 500 元、師傅已到場 800 元；已施工或已使用材料者，依實際工項或報價之 50% 計收。（依 ADR-0102，範例待確認）',
    'surcharge_clause', '現場如發現報價外之額外工項或材料，須先向客戶說明並取得重新確認同意後始行施作；未經同意不增項施作。（範例待確認）',
    'is_mock', true,
    'source', 'mock 範例待業主確認（CR-0046）'
  ),
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='company_profile' AND key='default');

-- 2. discount_policy（Q-11）— 報價核准門檻 + 客服折扣權限
INSERT INTO saas.config_namespace(code, description, json_schema) VALUES
  ('discount_policy',
   '報價核准門檻與客服折扣權限（CR-0046 / esales Q-11；範例待業主確認）',
   '{"type":"object","properties":{"approval_threshold":{"type":"number"},"cs_max_discount_pct":{"type":"number"},"supervisor_required_above_pct":{"type":"number"}}}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'discount_policy', 'default',
  '{"approval_threshold":10000,"cs_max_discount_pct":10,"supervisor_required_above_pct":10,"is_mock":true,"source":"mock 範例待業主確認（CR-0046）"}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version WHERE tenant_id IS NULL AND namespace='discount_policy' AND key='default');
