-- ============================================================================
-- Seed: 會計傳票（用於 /accounting/vouchers 全端 E2E）
-- ============================================================================
-- 涵蓋四種 related_entity_type：reconciliation / settlement / refund / invoice
-- 涵蓋正負金額（refund 為負，做沖銷帳）
-- 用法：
--   docker cp SQL/seeds/vouchers.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/vouchers.sql
-- ============================================================================

BEGIN;

-- 1) reconciliation：銀行入帳對齊月底結算（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111101'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260427-0001',
    'reconciliation', NULL,
    '1101', '1102',
    180000.00, 'TWD', '2026-04-27',
    '4 月份銀行對帳：玉山銀行入帳金額對齊',
    NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO NOTHING;

-- 2) settlement：技師月度結算（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111102'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260428-0001',
    'settlement', NULL,
    '5101', '2201',
    65000.00, 'TWD', '2026-04-28',
    '4 月份技師結算：王師傅 / 李師傅 / 陳師傅 三人',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

-- 3) refund：退款（負數沖銷，借貸對調）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111103'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260429-0001',
    'refund', NULL,
    '4001', '1101',
    -1500.00, 'TWD', '2026-04-29',
    '退款沖銷：客戶投訴後退費 NT$1,500',
    NOW() - INTERVAL '6 hours'
)
ON CONFLICT (id) DO NOTHING;

-- 4) invoice：服務收入入帳（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111104'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260429-0002',
    'invoice', NULL,
    '1101', '4001',
    3500.00, 'TWD', '2026-04-29',
    '工單服務費入帳：Chatlock AI-99 故障維修',
    NOW() - INTERVAL '3 hours'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
