-- ============================================================================
-- Seed: 負面情緒告警（用於 /admin/sentiment-alerts 全端 E2E）
-- ============================================================================
-- 目的：覆蓋三種狀態（pending / acknowledged / resolved）+ 兩種情緒標籤
--       （negative / very_negative）+ 不同關鍵字組合，方便後台 UI 過濾驗證。
-- 用法：
--   docker cp SQL/seeds/sentiment_alerts.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/sentiment_alerts.sql
-- 依賴：conversations.sql（須先跑），第 1 筆對話用於前 2 個告警，第 3 筆用於最後 1 個。
-- ============================================================================

BEGIN;

-- 1) pending — 高信心 very_negative，含「退費」+「投訴」
INSERT INTO sentiment_alerts (
    id, conversation_id, consumer_message,
    sentiment_label, confidence, detected_keywords,
    problem_card_id, status, notified_admin_ids,
    admin_note, created_at, updated_at
) VALUES (
    'aaaaaaaa-1111-4111-a111-111111111101'::uuid,
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '我已經反映三次都沒人理我，再不處理我就要去消保官投訴 + 退費！',
    'very_negative',
    0.92,
    ARRAY['退費','投訴','消保官'],
    NULL,
    'pending',
    NULL,
    NULL,
    NOW() - INTERVAL '15 minutes',
    NOW() - INTERVAL '15 minutes'
)
ON CONFLICT (id) DO NOTHING;

-- 2) acknowledged — 中等信心 negative，含「拖了很久」
INSERT INTO sentiment_alerts (
    id, conversation_id, consumer_message,
    sentiment_label, confidence, detected_keywords,
    problem_card_id, status, notified_admin_ids,
    admin_note, created_at, updated_at
) VALUES (
    'aaaaaaaa-1111-4111-a111-111111111102'::uuid,
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '已經拖了很久，我這幾天都不能回家欸',
    'negative',
    0.78,
    ARRAY['拖了很久','不能回家'],
    NULL,
    'acknowledged',
    NULL,
    '已聯繫客戶，預計今天 17:00 前派技師',
    NOW() - INTERVAL '2 hours',
    NOW() - INTERVAL '90 minutes'
)
ON CONFLICT (id) DO NOTHING;

-- 3) resolved — very_negative 已處置，含「律師」
INSERT INTO sentiment_alerts (
    id, conversation_id, consumer_message,
    sentiment_label, confidence, detected_keywords,
    problem_card_id, status, notified_admin_ids,
    admin_note, created_at, updated_at
) VALUES (
    'aaaaaaaa-1111-4111-a111-111111111103'::uuid,
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '我已經請律師了，請給我合理交代',
    'very_negative',
    0.95,
    ARRAY['律師','合理交代'],
    NULL,
    'resolved',
    NULL,
    '主管已親洽，協議全額退費並結案',
    NOW() - INTERVAL '2 days',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
