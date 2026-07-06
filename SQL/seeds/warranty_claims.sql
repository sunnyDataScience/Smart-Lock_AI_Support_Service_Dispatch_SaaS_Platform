-- Phase 1.24 warranty_claims seed — 5 筆涵蓋 active / grace / expired 三種保固期狀態
-- + filed / approved / rejected / in_progress / closed 五種 claim 狀態
-- customer_id 全部指向 test@lock-ai.com（c782bcfe...）方便 demo；
-- 實務上應指向 line_user，但 admin 已有 tenant_id 隔離，與表格欄位呈現無關。
-- 保固起算日以「交屋日期」為準（業務規則）。

BEGIN;

INSERT INTO warranty_claims (
    id, work_order_id, customer_id, device_brand, device_model,
    purchase_date, warranty_start_date, warranty_end_date, claim_date,
    is_within_warranty, status, dispute_reason, verification_source,
    resolution, discount_offered, created_at, updated_at
) VALUES
    -- WC1: filed — 保固有效充足（剩 ~10 個月）
    (
        '88888888-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa01',
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'Yale',
        'YDM-7116A',
        DATE '2025-12-15',
        DATE '2026-01-01',
        DATE '2027-01-01',
        DATE '2026-04-28',
        true,
        'filed',
        '裝置開鎖偶發無回應，懷疑指紋辨識模組異常',
        NULL,
        NULL,
        NULL,
        NOW() - INTERVAL '2 days',
        NOW() - INTERVAL '2 days'
    ),
    -- WC2: in_progress — 保固有效（剩 ~3 週寬限期）
    (
        '88888888-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02',
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'Chatlock',
        'AI-99',
        DATE '2025-04-10',
        DATE '2025-05-20',
        DATE '2026-05-20',
        DATE '2026-04-29',
        true,
        'in_progress',
        '韌體升級失敗導致裝置磚化',
        '原廠技術人員遠端確認',
        NULL,
        NULL,
        NOW() - INTERVAL '1 day',
        NOW() - INTERVAL '6 hours'
    ),
    -- WC3: approved — 已核准保固維修，保固期內
    (
        '88888888-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa03',
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        '美樂',
        'ML-88',
        DATE '2025-09-01',
        DATE '2025-10-15',
        DATE '2026-10-15',
        DATE '2026-04-20',
        true,
        'approved',
        '把手鬆動，無法正常上鎖',
        '客服電訪 + 工單照片',
        '同意原廠免費更換把手模組',
        NULL,
        NOW() - INTERVAL '8 days',
        NOW() - INTERVAL '5 days'
    ),
    -- WC4: rejected — 保固已過期，提供折讓
    (
        '88888888-aaaa-4aaa-aaaa-aaaaaaaaaa04',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'Samsung',
        'SHP-DP609',
        DATE '2024-04-01',
        DATE '2024-05-15',
        DATE '2025-05-15',
        DATE '2026-04-15',
        false,
        'rejected',
        '面板按鍵失靈，客戶要求免費維修',
        '系統交易紀錄 + 出貨單',
        '保固已過期 11 個月，提供 NT$500 折讓做為善意回應',
        500.00,
        NOW() - INTERVAL '14 days',
        NOW() - INTERVAL '12 days'
    ),
    -- WC5: closed — 保固即將到期（10 天內），已結案不維修
    (
        '88888888-aaaa-4aaa-aaaa-aaaaaaaaaa05',
        NULL,
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
        'Dormakaba',
        'c-lever pro',
        DATE '2025-04-15',
        DATE '2025-05-05',
        DATE '2026-05-05',
        DATE '2026-04-25',
        true,
        'closed',
        '螢幕背光偶發暗淡',
        '原廠工程師到府勘查',
        '經檢測屬正常使用範圍，無零件損壞，已向客戶說明',
        NULL,
        NOW() - INTERVAL '4 days',
        NOW() - INTERVAL '1 day'
    )
ON CONFLICT (id) DO NOTHING;

COMMIT;
