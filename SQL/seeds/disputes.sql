-- Phase 1.25 disputes seed — 5 筆涵蓋 5 種 dispute_type × 5 種 status 組合
-- filed_by 全部指向 test@lock-ai.com（c782bcfe...）讓 tenant 1 可見；
-- evidence (jsonb) 採 { customer: [...], technician: [...] } 結構，前端不渲染但保留結構真實。

BEGIN;

INSERT INTO disputes (
    id, work_order_id, invoice_id, filed_by, dispute_type, status,
    description, evidence, resolution, resolution_amount, resolved_by,
    filed_at, resolved_at, sla_deadline, created_at, updated_at
) VALUES
    -- D1: pricing × filed — 待處理，剛建立 6 小時前
    (
        '99999999-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'pricing',
        'filed',
        '客戶反映報價 NT$3500 高於原本承諾的 NT$2800，要求補回差額。',
        '{"customer": [{"type": "image", "ref": "evidence/D1-customer-quote.jpg"}], "technician": []}'::jsonb,
        NULL,
        NULL,
        NULL,
        NOW() - INTERVAL '6 hours',
        NULL,
        NOW() + INTERVAL '42 hours',
        NOW() - INTERVAL '6 hours',
        NOW() - INTERVAL '6 hours'
    ),
    -- D2: quality × in_review — 調解中，雙方證據齊全
    (
        '99999999-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'quality',
        'in_review',
        '鎖具安裝後無法正常開啟，多次嘗試後仍無法使用，要求重新安裝或退費。',
        '{"customer": [{"type": "image", "ref": "evidence/D2-customer-1.jpg"}, {"type": "image", "ref": "evidence/D2-customer-2.jpg"}], "technician": [{"type": "image", "ref": "evidence/D2-tech-checklist.jpg"}, {"type": "image", "ref": "evidence/D2-tech-test.jpg"}]}'::jsonb,
        NULL,
        NULL,
        NULL,
        NOW() - INTERVAL '2 days',
        NULL,
        NOW() + INTERVAL '1 day',
        NOW() - INTERVAL '2 days',
        NOW() - INTERVAL '12 hours'
    ),
    -- D3: warranty × resolved — 已結案，部分退款 NT$3500
    (
        '99999999-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'warranty',
        'resolved',
        '保固期內鎖具故障，客戶與技師對是否屬於保固範圍有爭議；最終判定屬保固範圍。',
        '{"customer": [{"type": "image", "ref": "evidence/D3-customer-purchase.jpg"}], "technician": [{"type": "image", "ref": "evidence/D3-tech-report.jpg"}]}'::jsonb,
        '雙方協議部分退款 NT$3500，並由技師重新安裝。',
        3500.00,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        NOW() - INTERVAL '8 days',
        NOW() - INTERVAL '5 days',
        NOW() - INTERVAL '6 days',
        NOW() - INTERVAL '8 days',
        NOW() - INTERVAL '5 days'
    ),
    -- D4: cancellation_fee × rejected — 已駁回，技師取消費爭議
    (
        '99999999-aaaa-4aaa-aaaa-aaaaaaaaaa04',
        NULL,
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'cancellation_fee',
        'rejected',
        '客戶於技師到場前 30 分鐘取消，要求免除取消費 NT$500。',
        '{"customer": [{"type": "text", "content": "因家中臨時有事取消"}], "technician": [{"type": "image", "ref": "evidence/D4-tech-route.jpg"}]}'::jsonb,
        '依平台規則取消費於到場前 1 小時內取消即收取，駁回客戶請求。',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        NOW() - INTERVAL '12 days',
        NOW() - INTERVAL '10 days',
        NOW() - INTERVAL '11 days',
        NOW() - INTERVAL '12 days',
        NOW() - INTERVAL '10 days'
    ),
    -- D5: settlement × closed — 已關閉，技師結算金額爭議
    (
        '99999999-aaaa-4aaa-aaaa-aaaaaaaaaa05',
        NULL,
        '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'settlement',
        'closed',
        '技師認為結算單漏列加班服務費，要求補發。經系統紀錄比對後確認無誤，案件關閉。',
        '{"customer": [], "technician": [{"type": "image", "ref": "evidence/D5-tech-timesheet.jpg"}]}'::jsonb,
        '系統時數紀錄與結算單一致，無遺漏；案件關閉。',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        NOW() - INTERVAL '20 days',
        NOW() - INTERVAL '15 days',
        NOW() - INTERVAL '18 days',
        NOW() - INTERVAL '20 days',
        NOW() - INTERVAL '15 days'
    )
ON CONFLICT (id) DO NOTHING;

COMMIT;
