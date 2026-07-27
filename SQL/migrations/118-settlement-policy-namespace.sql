-- migrate-targets: brand
-- ============================================================================
-- 118-settlement-policy-namespace.sql — 註冊 settlement_policy namespace（CR-0188）
-- ============================================================================
--
-- WHY：`monthly_settlement_service._assert_reconcile_gate` 讀 M18 config
--      `settlement_policy.reconcile_gate_enforce` 決定是否啟用 BR-SETTLE-05 對帳閘門，
--      但 **`settlement_policy` 這個 namespace 從未在任何 migration 註冊**
--      （全 repo 只有 service 與測試提到它）。而 `saas.config_version.namespace`
--      有 FK 指向 `saas.config_namespace(code)`（見 004），所以現況是
--      **這個開關根本插不進去、永遠開不了**——閘門形同不存在。
--
--      本檔只做「讓它變成可切換」，**value 寫 false ＝行為與現況完全相同**。
--
-- ⚠️ 刻意不在此檔開啟閘門。0727 紅隊審查發現閘門目前**設計上無法通過**：
--      `reconcile_commission` 查 legacy `public.settlements`，而月結
--      `generate_monthly_batch` 讀寫 v2 `saas.reconciliation/settlement`；且只有
--      legacy `approve_reconciliation` 會發 `commission.accrued`，v2 與月結兩條
--      寫入路徑都不發事件 → 投影永遠沒有 v2 的資料。貿然開啟＝每次月結永久 409。
--      修正屬另一個 CR（需先收斂 v2/legacy 表分裂或補事件發佈）。
--
-- is_protected=true：這是金流閘門，租戶不得自行 override 關閉
--   （config_m18_service._assert_namespace_writable：is_protected 且 tenant 層
--    override → 403 CONFIG_PROTECTED_OVERRIDE）。owner_role_codes 留空集合
--   ＝admin-only，比照 103 對 payment_gate 平台閘門的處置。
--
-- 全 idempotent（ON CONFLICT DO NOTHING / WHERE NOT EXISTS），可重複執行。
-- ============================================================================

-- 1) namespace 註冊（json_schema 為 NOT NULL，必須給值）
INSERT INTO saas.config_namespace(code, description, json_schema, owner_role_codes)
VALUES (
  'settlement_policy',
  '月結政策（BR-SETTLE-05 期末對帳閘門開關；CR-0188 註冊 namespace，預設 off）',
  '{"type":"object","properties":{"reconcile_gate_enforce":{"type":"boolean"}}}'::jsonb,
  '{}'::text[]           -- 空集合＝admin-only（金流閘門）
)
ON CONFLICT (code) DO NOTHING;

-- 2) 標為受保護（租戶不可 override 關閘）
UPDATE saas.config_namespace
   SET is_protected = TRUE
 WHERE code = 'settlement_policy';

-- 3) 全域預設值 = false（tenant_id NULL＝global；read_global_value 只讀 state='active'）
--    created_by 為 NOT NULL，沿用 044 的系統 seed uuid。
INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'settlement_policy', 'default',
  '{"reconcile_gate_enforce":false}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version
   WHERE namespace = 'settlement_policy' AND key = 'default' AND tenant_id IS NULL
);
