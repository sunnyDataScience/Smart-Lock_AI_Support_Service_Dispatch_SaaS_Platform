-- ============================================================================
-- Seed: 知識庫手冊（用於 GET /knowledge-base/manuals 列表展示）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/manuals.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/manuals.sql
-- 前置：必須先跑 Schema_api_phase1.sql（補 tenant_id + title 欄位）
-- ============================================================================
--
-- 種子內容：6 筆手冊，覆蓋 Yale / Chatlock / 美樂 三個品牌與 4 種狀態：
--   - completed (4)：可供 RAG 搜尋
--   - indexing  (1)：service 層 mapping 為 processing
--   - failed    (1)：標記錯誤訊息
--
-- 期望效果：
--   - GET /knowledge-base/manuals → 6 筆 items
--   - GET /knowledge-base/manuals?brand=Yale → 2 筆
--   - status mapping：completed → ready；indexing → processing
--   - title 欄位 fallback：NULL 時 service 層用 filename 去除副檔名展示
-- ============================================================================

BEGIN;

-- 1) Yale YDM-7220 — 完整手冊（completed）
INSERT INTO manuals (
    id, tenant_id, filename, title, brand, model,
    file_size_bytes, total_pages, total_chunks,
    status, created_at
)
VALUES (
    'aaaa1111-bbbb-4ccc-8ddd-eeeeeeee0001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Yale_YDM7220_使用手冊_v2.1.pdf',
    'Yale YDM-7220 使用手冊',
    'Yale',
    'YDM-7220',
    2_456_320,
    32,
    128,
    'completed',
    NOW() - INTERVAL '20 days'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, brand = EXCLUDED.brand, model = EXCLUDED.model,
    file_size_bytes = EXCLUDED.file_size_bytes, total_chunks = EXCLUDED.total_chunks,
    status = EXCLUDED.status;

-- 2) Yale YDM-3168 — 安裝指南（completed）
INSERT INTO manuals (
    id, tenant_id, filename, title, brand, model,
    file_size_bytes, total_pages, total_chunks,
    status, created_at
)
VALUES (
    'aaaa1111-bbbb-4ccc-8ddd-eeeeeeee0002'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Yale_YDM3168_Installation_Guide.pdf',
    'Yale YDM-3168 安裝指南',
    'Yale',
    'YDM-3168',
    1_843_200,
    24,
    96,
    'completed',
    NOW() - INTERVAL '14 days'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, brand = EXCLUDED.brand, model = EXCLUDED.model,
    file_size_bytes = EXCLUDED.file_size_bytes, total_chunks = EXCLUDED.total_chunks,
    status = EXCLUDED.status;

-- 3) Chatlock AI-99 — 進階功能手冊（completed，title 故意留 NULL 測 filename fallback）
INSERT INTO manuals (
    id, tenant_id, filename, title, brand, model,
    file_size_bytes, total_pages, total_chunks,
    status, created_at
)
VALUES (
    'aaaa1111-bbbb-4ccc-8ddd-eeeeeeee0003'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Chatlock_AI99_Advanced_Features.pdf',
    NULL,
    'Chatlock',
    'AI-99',
    3_276_800,
    48,
    192,
    'completed',
    NOW() - INTERVAL '7 days'
)
ON CONFLICT (id) DO UPDATE SET
    brand = EXCLUDED.brand, model = EXCLUDED.model,
    file_size_bytes = EXCLUDED.file_size_bytes, total_chunks = EXCLUDED.total_chunks,
    status = EXCLUDED.status;

-- 4) Chatlock A90 — 快速入門（indexing → service 層 mapping 為 processing）
INSERT INTO manuals (
    id, tenant_id, filename, title, brand, model,
    file_size_bytes, total_pages, total_chunks,
    status, created_at
)
VALUES (
    'aaaa1111-bbbb-4ccc-8ddd-eeeeeeee0004'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Chatlock_A90_QuickStart.pdf',
    'Chatlock A90 快速入門',
    'Chatlock',
    'A90',
    921_600,
    12,
    0,
    'indexing',
    NOW() - INTERVAL '2 days'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, brand = EXCLUDED.brand, model = EXCLUDED.model,
    file_size_bytes = EXCLUDED.file_size_bytes, total_chunks = EXCLUDED.total_chunks,
    status = EXCLUDED.status;

-- 5) 美樂 ML-9900 — 維修手冊（completed）
INSERT INTO manuals (
    id, tenant_id, filename, title, brand, model,
    file_size_bytes, total_pages, total_chunks,
    status, created_at
)
VALUES (
    'aaaa1111-bbbb-4ccc-8ddd-eeeeeeee0005'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    '美樂_ML9900_維修手冊.pdf',
    '美樂 ML-9900 維修手冊',
    '美樂',
    'ML-9900',
    4_152_320,
    56,
    224,
    'completed',
    NOW() - INTERVAL '30 days'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, brand = EXCLUDED.brand, model = EXCLUDED.model,
    file_size_bytes = EXCLUDED.file_size_bytes, total_chunks = EXCLUDED.total_chunks,
    status = EXCLUDED.status;

-- 6) 美樂 ML-3500 — 解析失敗（failed）
INSERT INTO manuals (
    id, tenant_id, filename, title, brand, model,
    file_size_bytes, total_pages, total_chunks,
    status, error_message, created_at
)
VALUES (
    'aaaa1111-bbbb-4ccc-8ddd-eeeeeeee0006'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    '美樂_ML3500_old_scan.pdf',
    '美樂 ML-3500 舊版掃描檔',
    '美樂',
    'ML-3500',
    5_242_880,
    NULL,
    0,
    'failed',
    'OCR 解析失敗：掃描品質過低，無法擷取文本',
    NOW() - INTERVAL '1 day'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, brand = EXCLUDED.brand, model = EXCLUDED.model,
    file_size_bytes = EXCLUDED.file_size_bytes,
    status = EXCLUDED.status, error_message = EXCLUDED.error_message;

COMMIT;

-- 驗證
SELECT id, brand, model, filename, title, status, total_chunks, file_size_bytes
FROM manuals
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY created_at DESC;
