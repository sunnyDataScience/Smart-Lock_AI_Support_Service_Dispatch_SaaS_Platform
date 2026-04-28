-- Phase 1.26 dispatch_logs seed — 8 筆涵蓋派工嘗試序列
-- 跨 3 筆 work_orders，模擬 1st/2nd/3rd 嘗試，含 reject/timeout/accept 三種終態
-- match_factors jsonb 結構：{"distance": 0.x, "skill": 0.x, "availability": 0.x}

BEGIN;

INSERT INTO dispatch_logs (
    id, work_order_id, action, technician_id, match_score, match_factors,
    rejection_reason, timeout_seconds, notes, created_at
) VALUES
    -- WO1 派工序列：1st assign → reject (距離太遠) → 2nd assign → timeout → 3rd assign (尚未回應)
    -- WO1 = 55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01 (Yale created)
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa01',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'assign',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        37.0,
        '{"distance": 0.20, "skill": 0.55, "availability": 0.40}'::jsonb,
        NULL, 300, NULL,
        NOW() - INTERVAL '45 minutes'
    ),
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa02',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'reject',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        37.0,
        NULL,
        '距離太遠，無法前往', NULL, NULL,
        NOW() - INTERVAL '40 minutes'
    ),
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa03',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'assign',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        45.0,
        '{"distance": 0.30, "skill": 0.55, "availability": 0.50}'::jsonb,
        NULL, 300, NULL,
        NOW() - INTERVAL '35 minutes'
    ),
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa04',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'timeout',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        45.0,
        NULL,
        NULL, 300, '5 分鐘內未回應，自動超時',
        NOW() - INTERVAL '30 minutes'
    ),
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa05',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'assign',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa04',
        78.0,
        '{"distance": 0.85, "skill": 0.70, "availability": 0.80}'::jsonb,
        NULL, 300, NULL,
        NOW() - INTERVAL '8 minutes'
    ),
    -- WO2 派工序列：1st assign → accept (高分一次到位)
    -- WO2 = 55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02 (Chatlock in_progress)
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa06',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        'assign',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        89.0,
        '{"distance": 0.92, "skill": 0.85, "availability": 0.90}'::jsonb,
        NULL, 300, NULL,
        NOW() - INTERVAL '2 hours'
    ),
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa07',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        'accept',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        89.0,
        NULL,
        NULL, NULL, '技師已接受',
        NOW() - INTERVAL '110 minutes'
    ),
    -- WO3 派工序列：1st assign → accept (已結案的歷史紀錄)
    -- WO3 = 55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03 (美樂 confirmed)
    (
        'aaaaaaaa-1111-4aaa-aaaa-aaaaaaaaaa08',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        'accept',
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa05',
        92.0,
        '{"distance": 0.95, "skill": 0.90, "availability": 0.92}'::jsonb,
        NULL, NULL, NULL,
        NOW() - INTERVAL '5 days'
    )
ON CONFLICT (id) DO NOTHING;

COMMIT;
