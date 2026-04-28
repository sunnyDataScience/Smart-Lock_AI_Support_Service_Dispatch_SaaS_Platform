-- ============================================================================
-- Seed: 對帳 + 結算（用於 GET /accounting/settlements 列表展示）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/settlements.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/settlements.sql
-- 前置：必須先跑 technicians.sql（取得技師 77777777…01）
-- ============================================================================
--
-- 種子內容：
--   - 1 名額外示範技師（無 user 帳號，僅出現在結算列表）：示範技師-王小英
--   - 4 筆 reconciliations（2 期 × 2 技師），全部 status='approved'
--   - 4 筆 settlements 覆蓋全部三個 status 與兩種 payment_method：
--       * pending  / bank_transfer  → 預期顯示「待付款」
--       * paid     / bank_transfer  → 預期顯示「已付款」+ paid_at
--       * paid     / other          → 「已付款」+ payment_method=other
--       * failed   / bank_transfer  → 「付款失敗」
--
-- 期望效果：
--   - GET /accounting/settlements → 4 筆 items
--   - ?status=pending → 1 筆
--   - ?status=paid    → 2 筆（bank_transfer + other 各 1）
--   - ?status=failed  → 1 筆
--   - ?technician_id=77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01 → 2 筆
-- ============================================================================

BEGIN;

-- 1) 第二名示範技師（無 user 帳號，純展示）
INSERT INTO technicians (
    id, tenant_id, user_id, name, phone, email,
    capabilities, service_regions,
    rating, completed_orders, status,
    created_at, updated_at
)
VALUES (
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NULL,
    '示範技師-王小英',
    '0922333444',
    'demo-wang@example.com',
    '["Yale", "Chatlock"]'::jsonb,
    '["台北市大安區", "新北市新店區"]'::jsonb,
    4.5, 18, 'active',
    NOW() - INTERVAL '60 days',
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    capabilities = EXCLUDED.capabilities,
    service_regions = EXCLUDED.service_regions;

-- 2) Reconciliations（2 期 × 2 技師 = 4 筆）
-- 林師傅 上月（已核准）
INSERT INTO reconciliations (
    id, technician_id, period_start, period_end,
    total_orders, total_revenue, platform_fee, technician_payout,
    status, approved_at, created_at
)
VALUES (
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc01'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    date_trunc('month', NOW() - INTERVAL '1 month'),
    date_trunc('month', NOW()) - INTERVAL '1 second',
    23, 138000.00, 27600.00, 110400.00,
    'approved',
    NOW() - INTERVAL '5 days',
    NOW() - INTERVAL '6 days'
)
ON CONFLICT (id) DO UPDATE SET
    total_orders = EXCLUDED.total_orders,
    technician_payout = EXCLUDED.technician_payout,
    status = EXCLUDED.status;

-- 林師傅 本月迄今（仍 pending）
INSERT INTO reconciliations (
    id, technician_id, period_start, period_end,
    total_orders, total_revenue, platform_fee, technician_payout,
    status, created_at
)
VALUES (
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc02'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    date_trunc('month', NOW()),
    NOW(),
    8, 48000.00, 9600.00, 38400.00,
    'pending',
    NOW() - INTERVAL '2 hours'
)
ON CONFLICT (id) DO UPDATE SET
    total_orders = EXCLUDED.total_orders,
    technician_payout = EXCLUDED.technician_payout;

-- 王小英 上月（已核准）
INSERT INTO reconciliations (
    id, technician_id, period_start, period_end,
    total_orders, total_revenue, platform_fee, technician_payout,
    status, approved_at, created_at
)
VALUES (
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc03'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    date_trunc('month', NOW() - INTERVAL '1 month'),
    date_trunc('month', NOW()) - INTERVAL '1 second',
    18, 102000.00, 20400.00, 81600.00,
    'approved',
    NOW() - INTERVAL '5 days',
    NOW() - INTERVAL '6 days'
)
ON CONFLICT (id) DO UPDATE SET
    total_orders = EXCLUDED.total_orders,
    technician_payout = EXCLUDED.technician_payout,
    status = EXCLUDED.status;

-- 王小英 上上月（已核准）
INSERT INTO reconciliations (
    id, technician_id, period_start, period_end,
    total_orders, total_revenue, platform_fee, technician_payout,
    status, approved_at, created_at
)
VALUES (
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc04'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    date_trunc('month', NOW() - INTERVAL '2 months'),
    date_trunc('month', NOW() - INTERVAL '1 month') - INTERVAL '1 second',
    21, 124000.00, 24800.00, 99200.00,
    'approved',
    NOW() - INTERVAL '35 days',
    NOW() - INTERVAL '36 days'
)
ON CONFLICT (id) DO UPDATE SET
    total_orders = EXCLUDED.total_orders,
    technician_payout = EXCLUDED.technician_payout,
    status = EXCLUDED.status;

-- 3) Settlements（4 筆覆蓋三個 status）
-- 3.1 林師傅 上月：已付款（bank_transfer）
INSERT INTO settlements (
    id, reconciliation_id, technician_id, amount, currency,
    status, payment_method, paid_at, created_at
)
VALUES (
    'dddd2222-aaaa-4aaa-bbbb-dddddddddd01'::uuid,
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc01'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    110400.00, 'TWD',
    'paid', 'bank_transfer',
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '5 days'
)
ON CONFLICT (id) DO UPDATE SET
    amount = EXCLUDED.amount, status = EXCLUDED.status,
    payment_method = EXCLUDED.payment_method, paid_at = EXCLUDED.paid_at;

-- 3.2 林師傅 本月：待付款（pending）
INSERT INTO settlements (
    id, reconciliation_id, technician_id, amount, currency,
    status, payment_method, paid_at, created_at
)
VALUES (
    'dddd2222-aaaa-4aaa-bbbb-dddddddddd02'::uuid,
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc02'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    38400.00, 'TWD',
    'pending', 'bank_transfer',
    NULL,
    NOW() - INTERVAL '1 hour'
)
ON CONFLICT (id) DO UPDATE SET
    amount = EXCLUDED.amount, status = EXCLUDED.status,
    paid_at = EXCLUDED.paid_at;

-- 3.3 王小英 上月：已付款（other 付款方式）
INSERT INTO settlements (
    id, reconciliation_id, technician_id, amount, currency,
    status, payment_method, paid_at, created_at
)
VALUES (
    'dddd2222-aaaa-4aaa-bbbb-dddddddddd03'::uuid,
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc03'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    81600.00, 'TWD',
    'paid', 'other',
    NOW() - INTERVAL '4 days',
    NOW() - INTERVAL '5 days'
)
ON CONFLICT (id) DO UPDATE SET
    amount = EXCLUDED.amount, status = EXCLUDED.status,
    payment_method = EXCLUDED.payment_method, paid_at = EXCLUDED.paid_at;

-- 3.4 王小英 上上月：付款失敗
INSERT INTO settlements (
    id, reconciliation_id, technician_id, amount, currency,
    status, payment_method, paid_at, created_at
)
VALUES (
    'dddd2222-aaaa-4aaa-bbbb-dddddddddd04'::uuid,
    'cccc1111-aaaa-4aaa-bbbb-cccccccccc04'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    99200.00, 'TWD',
    'failed', 'bank_transfer',
    NULL,
    NOW() - INTERVAL '34 days'
)
ON CONFLICT (id) DO UPDATE SET
    amount = EXCLUDED.amount, status = EXCLUDED.status,
    payment_method = EXCLUDED.payment_method, paid_at = EXCLUDED.paid_at;

COMMIT;

-- 驗證
SELECT s.id, t.name, s.amount, s.status, s.payment_method, s.paid_at, s.created_at
FROM settlements s
JOIN technicians t ON s.technician_id = t.id
WHERE t.tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY s.created_at DESC;
