-- ============================================================================
-- Seed: 工單（連到 problem_cards.sql 的 3 筆 PC，用於 /work-orders E2E
--      與 dashboard work_orders 三張 KPI：today_count / completion_rate /
--      overdue_count）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/work_orders.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/work_orders.sql
-- 前置：必須先跑 conversations.sql + problem_cards.sql
--      （依賴 44444444-...01/02/03 三筆 PC）
-- ============================================================================
--
-- 工單覆蓋情境（讓 dashboard 三張 KPI 都有值可秀）：
--   WO1：created（待派工）, scheduled_at = NOW + 2h, created_at = 今日
--        → today_count +1
--   WO2：in_progress, scheduled_at = NOW - 1h（已過排程），created_at = 今日
--        → today_count +1, overdue +1
--   WO3：confirmed（已結案）, completed_at = 今日, created_at = 今日
--        → today_count +1, completed +1 ⇒ completion_rate = 1/3 ≈ 33%
--
-- 期望 dashboard.work_orders = { today_count: 3, completion_rate: 0.333..,
--                                overdue_count: 1 }
-- ============================================================================

BEGIN;

-- ---------- WO1：對應 PC1（Yale, incomplete）→ 工單 created ----------
INSERT INTO work_orders (
    id, problem_card_id, status, priority,
    customer_name, customer_phone, customer_address,
    scheduled_at, estimated_price,
    created_at, updated_at
)
VALUES (
    '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '44444444-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    'created', 'normal',
    '王小明', '0912345678', '台北市信義區松仁路100號',
    NOW() + INTERVAL '2 hours', 1800,
    date_trunc('day', NOW()) + INTERVAL '8 hours',
    date_trunc('day', NOW()) + INTERVAL '8 hours'
)
ON CONFLICT (id) DO NOTHING;

-- ---------- WO2：對應 PC2（Chatlock, confirmed/L3）→ 工單 in_progress 且逾時 ----------
INSERT INTO work_orders (
    id, problem_card_id, status, priority,
    customer_name, customer_phone, customer_address,
    scheduled_at, started_at, estimated_price,
    created_at, updated_at
)
VALUES (
    '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    '44444444-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    'in_progress', 'high',
    '陳美麗', '0922334455', '新北市板橋區中山路二號 88 號',
    NOW() - INTERVAL '1 hour', NOW() - INTERVAL '30 minutes', 3500,
    date_trunc('day', NOW()) + INTERVAL '6 hours',
    NOW() - INTERVAL '30 minutes'
)
ON CONFLICT (id) DO NOTHING;

-- ---------- WO3：對應 PC3（美樂, resolved）→ 工單 confirmed（今日完工） ----------
INSERT INTO work_orders (
    id, problem_card_id, status, priority,
    customer_name, customer_phone, customer_address,
    scheduled_at, started_at, completed_at, confirmed_at,
    estimated_price, final_price,
    created_at, updated_at
)
VALUES (
    '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '44444444-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    'confirmed', 'low',
    '林志強', '0933445566', '桃園市中壢區中央西路一段 50 號',
    date_trunc('day', NOW()) + INTERVAL '9 hours',
    date_trunc('day', NOW()) + INTERVAL '9 hours 15 minutes',
    date_trunc('day', NOW()) + INTERVAL '10 hours',
    date_trunc('day', NOW()) + INTERVAL '10 hours 5 minutes',
    1200, 1200,
    date_trunc('day', NOW()) + INTERVAL '7 hours',
    date_trunc('day', NOW()) + INTERVAL '10 hours 5 minutes'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- 驗證
SELECT wo.id, pc.brand, pc.model, wo.status, wo.priority,
       wo.customer_address, wo.estimated_price,
       wo.created_at::date AS created_date, wo.scheduled_at, wo.completed_at
FROM work_orders wo
JOIN problem_cards pc ON wo.problem_card_id = pc.id
JOIN conversations c ON pc.conversation_id = c.id
JOIN users u ON c.user_id = u.id
WHERE u.tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY wo.created_at DESC;
