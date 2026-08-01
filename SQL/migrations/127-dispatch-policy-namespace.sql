-- migrate-targets: brand
-- ============================================================================
-- 127-dispatch-policy-namespace.sql — 註冊 dispatch_policy namespace（CR-0197 D1(c)）
-- ============================================================================
--
-- WHY：業主 2026-08-01 對 CR-0197 §8 D1 裁決選 (c) 折衷 —— 品牌授權閘門改為
--      fail-closed，但由 M18 config `dispatch_policy.brand_auth_enforce` 控制，
--      **預設 off**，等營運補齊授權名單後逐租戶開啟。
--
--      背景（CR-0197 §4 prod 唯讀盤點）：`technician_brand_authorization` 目前
--      只有 Generic/Kaadas/Philips/Samsung/Yale 各 13 筆——正是 CR-0060 的
--      `is_mock` seed 原封不動，**營運從未填過真實資料**。而實際在用的
--      Chatlock/Dormakaba/美樂/Xiaomi/Gateman 一筆都沒有。硬性啟用 fail-closed
--      會讓這些品牌的單無法自動派工（手動派工仍可由主管 override_reason 通過）。
--
-- ⚠️ 沿用 118 的教訓：`saas.config_version.namespace` 有 FK 指向
--      `saas.config_namespace(code)`（見 004）。**namespace 沒註冊，開關就插不進去、
--      永遠開不了**——118 就是為了修這個坑而生。本檔先把 namespace 建起來，
--      value 寫 false ＝行為與現況完全相同。
--
-- is_protected=true：派工資格是准入閘門（04_SRS.md FR-TEC-02 驗收「未過准入閘門
--      不得進入派工候選集」），不得由租戶自行 override 關閉。owner_role_codes
--      留空集合＝admin-only，比照 103（payment_gate）與 118（settlement_policy）。
--
-- 全 idempotent（ON CONFLICT DO NOTHING / WHERE NOT EXISTS），可重複執行。
-- ============================================================================

-- 1) namespace 註冊（json_schema 為 NOT NULL，必須給值）
INSERT INTO saas.config_namespace(code, description, json_schema, owner_role_codes)
VALUES (
  'dispatch_policy',
  '派工政策（FR-TEC-02/FR-TEC-03 品牌授權准入閘門開關；CR-0197 註冊 namespace，預設 off）',
  '{"type":"object","properties":{"brand_auth_enforce":{"type":"boolean"}}}'::jsonb,
  '{}'::text[]           -- 空集合＝admin-only（准入閘門）
)
ON CONFLICT (code) DO NOTHING;

-- 2) 標為受保護（租戶不可 override 關閘）
UPDATE saas.config_namespace
   SET is_protected = TRUE
 WHERE code = 'dispatch_policy';

-- 3) 全域預設值 = false（tenant_id NULL＝global；read_global_value 只讀 state='active'）
--    created_by 為 NOT NULL，沿用 044 的系統 seed uuid。
INSERT INTO saas.config_version (tenant_id, namespace, key, value, state, created_by, activated_at)
SELECT NULL, 'dispatch_policy', 'default',
  '{"brand_auth_enforce":false}'::jsonb,
  'active', '00000000-0000-0000-0000-000000000001', now()
WHERE NOT EXISTS (
  SELECT 1 FROM saas.config_version
   WHERE namespace = 'dispatch_policy' AND key = 'default' AND tenant_id IS NULL
);
