-- Phase 1.21 invoices seed — 3 筆對應 work_orders.sql 的 WO1/WO2/WO3
-- DB invoices.work_order_id 有 UNIQUE 約束，所以一張工單只能對應一張發票。
-- 狀態涵蓋三種 API 對齊：paid → issued / draft → pending / cancelled → voided

BEGIN;

INSERT INTO invoices (
    id, work_order_id, invoice_number, amount, tax, total, status,
    line_items, issued_at, paid_at, created_at, updated_at
) VALUES
    -- WO3 (closed) → paid invoice，已開立並完款
    (
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        'AB10000001',
        1200.00, 60.00, 1260.00,
        'paid',
        '[{"name":"美樂電子鎖開鎖服務","qty":1,"unit_price":1200.00}]'::jsonb,
        NOW() - INTERVAL '2 days',
        NOW() - INTERVAL '1 day',
        NOW() - INTERVAL '2 days',
        NOW() - INTERVAL '1 day'
    ),
    -- WO2 (in_progress) → draft invoice，尚未開立
    (
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        'AB10000002',
        3500.00, 175.00, 3675.00,
        'draft',
        '[{"name":"Chatlock AI-99 韌體升級","qty":1,"unit_price":3500.00}]'::jsonb,
        NULL,
        NULL,
        NOW() - INTERVAL '5 hours',
        NOW() - INTERVAL '5 hours'
    ),
    -- WO1 (created) → cancelled invoice，已作廢（demo voided 狀態）
    (
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'AB10000003',
        1800.00, 90.00, 1890.00,
        'cancelled',
        '[{"name":"Yale 智慧鎖故障排除","qty":1,"unit_price":1800.00}]'::jsonb,
        NOW() - INTERVAL '6 hours',
        NULL,
        NOW() - INTERVAL '6 hours',
        NOW() - INTERVAL '3 hours'
    )
ON CONFLICT (id) DO NOTHING;

COMMIT;
