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

-- ============================================================================
-- 6 月份傳票：posting_date 落在預設「近 30 天」範圍內，頁面開啟即可見
-- （上方 4 月份資料需手動把日期範圍拉回 4 月才看得到）。
-- ============================================================================

-- 5) invoice：服務收入入帳（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111201'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260605-0001',
    'invoice', NULL,
    '1101', '4001',
    4200.00, 'TWD', '2026-06-05',
    '工單服務費入帳：美樂 ML-30 安裝',
    NOW() - INTERVAL '25 days'
)
ON CONFLICT (id) DO NOTHING;

-- 6) reconciliation：銀行入帳對齊（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111202'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260610-0001',
    'reconciliation', NULL,
    '1101', '1102',
    95000.00, 'TWD', '2026-06-10',
    '6 月份銀行對帳：玉山銀行入帳金額對齊',
    NOW() - INTERVAL '20 days'
)
ON CONFLICT (id) DO NOTHING;

-- 7) settlement：技師月度結算（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111203'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260615-0001',
    'settlement', NULL,
    '5101', '2201',
    72000.00, 'TWD', '2026-06-15',
    '5 月份技師結算：丁師傅 / 林師傅 / 黃師傅 三人',
    NOW() - INTERVAL '15 days'
)
ON CONFLICT (id) DO NOTHING;

-- 8) refund：退款（負數沖銷，借貸對調）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111204'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260618-0001',
    'refund', NULL,
    '4001', '1101',
    -2800.00, 'TWD', '2026-06-18',
    '退款沖銷：重複收費更正退費 NT$2,800',
    NOW() - INTERVAL '12 days'
)
ON CONFLICT (id) DO NOTHING;

-- 9) invoice：服務收入入帳（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111205'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260624-0001',
    'invoice', NULL,
    '1101', '4001',
    6800.00, 'TWD', '2026-06-24',
    '工單服務費入帳：Samsung SHP-DR719 故障維修 + 換料',
    NOW() - INTERVAL '6 days'
)
ON CONFLICT (id) DO NOTHING;

-- 10) reconciliation：銀行入帳對齊（正數）
INSERT INTO vouchers (
    id, tenant_id, voucher_number,
    related_entity_type, related_entity_id,
    debit_account, credit_account,
    amount, currency, posting_date, memo, created_at
) VALUES (
    'cccccccc-1111-4111-c111-111111111206'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'V20260629-0001',
    'reconciliation', NULL,
    '1101', '1102',
    120000.00, 'TWD', '2026-06-29',
    '6 月份銀行對帳：國泰世華入帳金額對齊',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
