-- ============================================================================
-- Seed: 計價規則（用於 GET /pricing/rules 列表展示）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/pricing_rules.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/pricing_rules.sql
-- 前置：必須先跑 Schema_api_phase1.sql（取得 price_rules.tenant_id 欄位）
-- ============================================================================
--
-- 種子內容：
--   - 4 筆 price_rules 覆蓋 3 brand × difficulty 與 lock_type 多樣性
--   - 含 1 筆 is_active=FALSE 用於驗證 service 過濾邏輯
--   - modifiers 採 array form：[{name, condition, amount}, ...]
--
-- DB↔OpenAPI 對齊（service 層處理）：
--   - difficulty: easy→simple、medium→moderate、hard→complex
--   - base_price FLOAT → decimal string with 2 decimals
--   - modifiers JSONB array → surcharges[]（PricingSurcharge schema）
--
-- 期望效果：
--   - GET /pricing/rules → 3 筆 items（is_active=FALSE 那筆會被過濾掉）
--   - ?brand=Yale → 1 筆
--   - ?brand=Chatlock → 1 筆（is_active=FALSE 排除後 0）→ 故意保留 Chatlock 兩筆
-- ============================================================================

BEGIN;

-- 1) Yale digital_deadbolt easy（基礎價，無加價）
INSERT INTO price_rules (
    id, tenant_id, brand, lock_type, difficulty,
    base_price, labor_cost, parts_cost, modifiers, is_active,
    created_at, updated_at
)
VALUES (
    'eeee3333-aaaa-4aaa-bbbb-eeeeeeeeee01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Yale', 'digital_deadbolt', 'easy',
    1200.00, 800.00, 100.00,
    '[]'::jsonb,
    TRUE,
    NOW() - INTERVAL '30 days',
    NOW() - INTERVAL '30 days'
)
ON CONFLICT (id) DO UPDATE SET
    base_price = EXCLUDED.base_price,
    modifiers = EXCLUDED.modifiers,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- 2) Chatlock smart_lock medium（含夜間 + 假日加價）
INSERT INTO price_rules (
    id, tenant_id, brand, lock_type, difficulty,
    base_price, labor_cost, parts_cost, modifiers, is_active,
    created_at, updated_at
)
VALUES (
    'eeee3333-aaaa-4aaa-bbbb-eeeeeeeeee02'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Chatlock', 'smart_lock', 'medium',
    2500.00, 1500.00, 500.00,
    '[
        {"name": "夜間服務", "condition": "22:00 - 06:00", "amount": 500.00},
        {"name": "假日服務", "condition": "週六、日及國定假日", "amount": 300.00}
    ]'::jsonb,
    TRUE,
    NOW() - INTERVAL '20 days',
    NOW() - INTERVAL '20 days'
)
ON CONFLICT (id) DO UPDATE SET
    base_price = EXCLUDED.base_price,
    modifiers = EXCLUDED.modifiers,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- 3) Dormakaba smart_lock hard（緊急派工加價）
INSERT INTO price_rules (
    id, tenant_id, brand, lock_type, difficulty,
    base_price, labor_cost, parts_cost, modifiers, is_active,
    created_at, updated_at
)
VALUES (
    'eeee3333-aaaa-4aaa-bbbb-eeeeeeeeee03'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Dormakaba', 'smart_lock', 'hard',
    4500.00, 2800.00, 1200.00,
    '[
        {"name": "緊急派工", "condition": "2 小時內到場", "amount": 1500.00},
        {"name": "偏遠地區", "condition": "距離 > 30km", "amount": 800.00}
    ]'::jsonb,
    TRUE,
    NOW() - INTERVAL '10 days',
    NOW() - INTERVAL '10 days'
)
ON CONFLICT (id) DO UPDATE SET
    base_price = EXCLUDED.base_price,
    modifiers = EXCLUDED.modifiers,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- 4) 已停用規則（is_active=FALSE 應被 service 過濾）
INSERT INTO price_rules (
    id, tenant_id, brand, lock_type, difficulty,
    base_price, labor_cost, parts_cost, modifiers, is_active,
    created_at, updated_at
)
VALUES (
    'eeee3333-aaaa-4aaa-bbbb-eeeeeeeeee04'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Yale', 'padlock', 'easy',
    600.00, 400.00, 50.00,
    '[]'::jsonb,
    FALSE,
    NOW() - INTERVAL '90 days',
    NOW() - INTERVAL '60 days'
)
ON CONFLICT (id) DO UPDATE SET
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

COMMIT;

-- 驗證
SELECT id, brand, lock_type, difficulty, base_price, is_active,
       jsonb_array_length(COALESCE(modifiers, '[]'::jsonb)) AS surcharge_count
FROM price_rules
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY created_at DESC;
