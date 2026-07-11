-- 103-config-namespace-owner-protected.sql
--
-- WHY（CR-0166 R1-6 + R1-7）：
--   R1-6 受保護層：M18 config 無「平台級受保護 key」機制——任何 namespace 的租戶層
--     override 都能覆寫（UF-08 §9.3 S5 要求 protected override 被擋，無實作）。
--   R1-7 owner_role_codes 死欄位：欄位存在但寫死 admin-only，per-namespace owner
--     治理未落地（例：pricing 類 namespace 應限 operations_manager）。
--
-- WHAT：
--   1. config_namespace 加 is_protected boolean（NOT NULL DEFAULT false）。
--   2. 回填各 namespace 的 owner_role_codes（財務/政策/字典類→operations_manager；
--      payment_gate 平台閘門→admin-only 空集合＋is_protected=true）。
--   idempotent：ADD COLUMN IF NOT EXISTS + 具名 UPDATE（可重套，值固定）。
--
-- 語意（service 層 _assert_namespace_writable 消費）：
--   - is_protected=true 且 tenant 層 override（tenant_id 非 NULL）→ 403 CONFIG_PROTECTED_OVERRIDE。
--   - owner_role_codes 非空 → actor_role 須 ∈ owner_role_codes 或 admin（admin 永遠 bypass）。
--   - owner_role_codes 空 → fallback admin-only（＝現行為，未回填前零行為變化）。

ALTER TABLE saas.config_namespace
    ADD COLUMN IF NOT EXISTS is_protected boolean NOT NULL DEFAULT false;

-- 財務金額 / 政策 / 字典 / 文案類：operations_manager 可改（admin 隱含 bypass）
UPDATE saas.config_namespace
SET owner_role_codes = ARRAY['operations_manager']
WHERE code IN (
    'cancellation_fee_tiers', 'refund_tier_thresholds', 'travel_fee_distance_tiers',
    'deposit_policy', 'dispatch_commission', 'monthly_close_schedule', 'tax_policy',
    'discount_policy', 'quote_policy', 'quote_validity_policy',
    'completion_policy', 'problemcard_policy', 'scope_change_policy',
    'auto_confirm_policy', 'sla_dispatch', 'sla_policy',
    'cancellation_reason_codes', 'technician_suspension_reasons', 'company_profile'
)
AND owner_role_codes = '{}';

-- 平台閘門：payment_gate 鎖 admin-only（owner 空集合）＋受保護（租戶不可 override）
UPDATE saas.config_namespace
SET is_protected = true
WHERE code = 'payment_gate';

COMMENT ON COLUMN saas.config_namespace.is_protected IS
'CR-0166 R1-6：受保護層——true 時租戶層 override 被擋（僅平台級可改）';
COMMENT ON COLUMN saas.config_namespace.owner_role_codes IS
'CR-0166 R1-7：per-namespace owner 角色（非空＝限這些角色寫入；空＝admin-only fallback；admin 永遠 bypass）';
