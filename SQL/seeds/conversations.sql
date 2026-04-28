-- ============================================================================
-- Seed: 對話 + 訊息（用於 /conversations 全端 E2E）
-- ============================================================================
-- 目的：建立可重現的種子資料，覆蓋 OpenAPI 三個 status：
--   active / waiting_human / closed
-- 用法：
--   docker cp SQL/seeds/conversations.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/conversations.sql
-- ============================================================================

BEGIN;

-- 1) LINE 消費者（admin tenant）
INSERT INTO users (id, tenant_id, line_user_id, display_name, role, is_active)
VALUES (
    '11111111-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'U' || repeat('a', 32),
    '王小明',
    'line_user',
    TRUE
)
ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name;

-- 2) 三筆對話（active / waiting_human / closed）
-- ---------- A. active ----------
INSERT INTO conversations (id, user_id, session_id, status, channel, message_count, started_at, created_at, updated_at)
VALUES (
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '11111111-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    'sess-active-1',
    'active',
    'line',
    2,
    NOW() - INTERVAL '15 minutes',
    NOW() - INTERVAL '15 minutes',
    NOW() - INTERVAL '5 minutes'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO messages (id, conversation_id, role, content_type, content, created_at)
VALUES
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
   'user', 'text', '我家的智慧鎖門打不開了，按鍵也沒反應',
   NOW() - INTERVAL '15 minutes'),
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
   'assistant', 'text', '請問您使用的是哪個品牌與型號？我可以協助您快速排查。',
   NOW() - INTERVAL '14 minutes')
ON CONFLICT (id) DO NOTHING;

-- ---------- B. waiting_human (DB: escalated) ----------
INSERT INTO conversations (id, user_id, session_id, status, channel, resolution_layer, message_count, started_at, created_at, updated_at)
VALUES (
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    '11111111-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    'sess-waiting-1',
    'escalated',
    'line',
    NULL,
    3,
    NOW() - INTERVAL '2 hours',
    NOW() - INTERVAL '2 hours',
    NOW() - INTERVAL '30 minutes'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO messages (id, conversation_id, role, content_type, content, metadata, created_at)
VALUES
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa11'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
   'user', 'image', '[使用者上傳了一張鎖具照片]',
   '{"image_url": "https://example.com/lock-photo.jpg"}'::jsonb,
   NOW() - INTERVAL '2 hours'),
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa12'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
   'assistant', 'text', '我看到照片了，這個情況需要技師到場檢測，已為您建立轉接服務。',
   NULL,
   NOW() - INTERVAL '1 hour 50 minutes'),
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa13'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
   'system', 'text', '已升級至客服專員，等候人工回覆中。',
   NULL,
   NOW() - INTERVAL '30 minutes')
ON CONFLICT (id) DO NOTHING;

-- ---------- C. closed (DB: resolved) ----------
INSERT INTO conversations (id, user_id, session_id, status, channel, resolution_layer, message_count, started_at, resolved_at, created_at, updated_at)
VALUES (
    '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '11111111-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    'sess-closed-1',
    'resolved',
    'line',
    'L2',
    3,
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days' + INTERVAL '20 minutes',
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '3 days' + INTERVAL '20 minutes'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO messages (id, conversation_id, role, content_type, content, created_at)
VALUES
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa21'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
   'user', 'text', '智慧鎖的保固期是多久？',
   NOW() - INTERVAL '3 days'),
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa22'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
   'assistant', 'text', '依據原廠手冊，主機保固 2 年、電池保固 6 個月，安裝日起算。',
   NOW() - INTERVAL '3 days' + INTERVAL '5 minutes'),
  ('33333333-aaaa-4aaa-aaaa-aaaaaaaaaa23'::uuid,
   '22222222-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
   'user', 'text', '謝謝！',
   NOW() - INTERVAL '3 days' + INTERVAL '10 minutes')
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- 驗證
SELECT c.id, c.status, c.resolution_layer, c.message_count, u.line_user_id
FROM conversations c JOIN users u ON c.user_id = u.id
WHERE u.tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY c.created_at DESC;
