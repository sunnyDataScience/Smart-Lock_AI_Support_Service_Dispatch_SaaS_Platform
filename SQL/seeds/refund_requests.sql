-- Phase 1.23 refund_requests seed — 4 筆對應 work_orders/invoices.sql 的 WO/Invoice
-- 涵蓋 4 種 API 狀態 + 2 種 SLA 區段（剛申請 / 接近 8 小時）
-- requested_by 全部指向 admin@example.com（c782bcfe...），代表客服代客申請

BEGIN;

INSERT INTO refund_requests (
    id, work_order_id, invoice_id, complaint_id, requested_by,
    amount, reason, status, approval_chain, requires_dual_sign,
    executed_at, created_at, updated_at
) VALUES
    -- RR1: pending — 剛申請，SLA 充足（小金額不需雙簽）
    (
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        1200.00,
        '客戶反映美樂電子鎖開鎖後三天內再次故障，要求全額退款',
        'pending',
        '[]'::jsonb,
        false,
        NULL,
        NOW() - INTERVAL '30 minutes',
        NOW() - INTERVAL '30 minutes'
    ),
    -- RR2: escalated — 大金額已升級到主管，SLA 接近 8 小時上限（需雙簽）
    (
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        3500.00,
        'Chatlock AI-99 韌體升級失敗導致裝置磚化，客戶要求退款並補償',
        'escalated',
        '[{"actor":"admin@example.com","decision":"escalate","reason":"金額超過授權額度","at":"2026-04-28T18:00:00Z"}]'::jsonb,
        true,
        NULL,
        NOW() - INTERVAL '7 hours' - INTERVAL '20 minutes',
        NOW() - INTERVAL '6 hours'
    ),
    -- RR3: approved — 已核准但尚未執行（核准與執行為兩階段）
    (
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        1800.00,
        'Yale 智慧鎖工單取消，客戶已收到車馬費收費抗議，同意退款',
        'approved',
        '[{"actor":"admin@example.com","decision":"approve","reason":"工單未派遣，車馬費應退","at":"2026-04-28T22:00:00Z"}]'::jsonb,
        false,
        NULL,
        NOW() - INTERVAL '4 hours',
        NOW() - INTERVAL '2 hours'
    ),
    -- RR4: executed — 已完款（最終狀態，無關聯發票）
    (
        '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa04',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        NULL,
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        500.00,
        '美樂電子鎖工單部分折讓（耗材費爭議）',
        'executed',
        '[{"actor":"admin@example.com","decision":"approve","reason":"折讓 NT$500","at":"2026-04-26T10:00:00Z"},{"actor":"admin@example.com","decision":"execute","reason":"已透過第三方支付退款","at":"2026-04-27T15:00:00Z"}]'::jsonb,
        false,
        NOW() - INTERVAL '2 days',
        NOW() - INTERVAL '3 days',
        NOW() - INTERVAL '2 days'
    )
ON CONFLICT (id) DO NOTHING;

COMMIT;
