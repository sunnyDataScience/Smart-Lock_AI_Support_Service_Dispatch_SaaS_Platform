-- ============================================================================
-- Seed: 問題卡（連到 conversations.sql 的 3 筆對話，用於 /problem-cards E2E
--      與 dashboard hot_topics / top_brands 真實資料）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/problem_cards.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/problem_cards.sql
-- 前置：必須先跑 conversations.sql（依賴 22222222-...01/02/03 三筆 conversation）
-- ============================================================================

BEGIN;

-- ---------- A. active conversation → draft PC (Yale, urgency=normal, category=密碼) ----------
INSERT INTO problem_cards (
    id, conversation_id, brand, model, category, location,
    door_status, network_status, symptoms, urgency, intent,
    status, completeness_score, created_at, updated_at
)
VALUES (
    '44444444-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    'Yale', 'YDM-4109', '密碼', '台北市信義區',
    'partially_functional', 'unknown',
    '["按鍵無反應", "輸入密碼無回饋"]'::jsonb,
    'normal', 'repair',
    'incomplete', 0.45,
    NOW() - INTERVAL '14 minutes',
    NOW() - INTERVAL '5 minutes'
)
ON CONFLICT (id) DO NOTHING;

-- ---------- B. waiting_human conversation → confirmed PC (Chatlock, urgency=high, category=故障) ----------
INSERT INTO problem_cards (
    id, conversation_id, brand, model, category, location,
    door_status, network_status, symptoms, urgency, intent,
    status, completeness_score, resolution_layer,
    media_urls, created_at, updated_at
)
VALUES (
    '44444444-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    'Chatlock', 'AI-99', '故障', '新北市板橋區',
    'locked_out', 'offline',
    '["鎖體鬆動", "面板閃爍"]'::jsonb,
    'high', 'repair',
    'confirmed', 0.85, 'L3',
    '["https://example.com/lock-photo.jpg"]'::jsonb,
    NOW() - INTERVAL '1 hour 50 minutes',
    NOW() - INTERVAL '30 minutes'
)
ON CONFLICT (id) DO NOTHING;

-- ---------- C. closed conversation → resolved PC (美樂, urgency=low, category=安裝) ----------
INSERT INTO problem_cards (
    id, conversation_id, brand, model, category, location,
    door_status, network_status, symptoms, urgency, intent,
    status, completeness_score, resolution_layer,
    created_at, updated_at
)
VALUES (
    '44444444-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '美樂', 'ENTR', '安裝', '桃園市中壢區',
    'normal', 'online',
    '["保固查詢"]'::jsonb,
    'low', 'inquiry',
    'resolved', 1.0, 'L2',
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days' + INTERVAL '20 minutes'
)
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- 驗證
SELECT pc.id, pc.brand, pc.model, pc.category, pc.urgency, pc.status, pc.symptoms
FROM problem_cards pc
JOIN conversations c ON pc.conversation_id = c.id
JOIN users u ON c.user_id = u.id
WHERE u.tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY pc.created_at DESC;
