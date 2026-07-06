-- ============================================================================
-- Seed: 技師（用於 GET /technicians/me/* E2E 與 dashboard technicians KPI）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/technicians.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/technicians.sql
-- 前置：必須先跑 work_orders.sql（會把 WO2 的 technician_id 指向本檔的技師）
-- ============================================================================
--
-- 種子內容：
--   - 1 名啟用中技師（status='active'），對應 users.role='technician'
--   - 將 work_orders.sql 的 WO2 (in_progress) 指派給此技師
--
-- 期望效果：
--   - GET /technicians/me（需登入 test@lock-ai.com / changeme123）→ 200
--   - GET /technicians（admin 視角）→ 5 筆（1 名登入示範 + 4 名展示用）
--   - dashboard.technicians = { total_count: 5, online_count: 4, dispatchable_count: 4 }
--     （5 名 active；其中 demo-tech 有 in_progress 工單，故 online_count = 4）
-- ============================================================================

BEGIN;

-- 1) demo 技師對應的 user 帳號（role='technician'）
-- password = changeme123（bcrypt,與 _admin_user.sql 同一 hash;2026-07-06 測試帳號密碼統一）
INSERT INTO users (
    id, tenant_id, email, password_hash, display_name, phone, role, is_active
)
VALUES (
    '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'test@lock-ai.com',
    '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
    '示範技師-林師傅',
    '0911222333',
    'technician',
    TRUE
)
ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    display_name = EXCLUDED.display_name,
    phone = EXCLUDED.phone,
    is_active = EXCLUDED.is_active;

-- 2) technicians 表（status='active'）
INSERT INTO technicians (
    id, tenant_id, user_id, name, phone, email,
    capabilities, service_regions,
    rating, completed_orders, status,
    created_at, updated_at
)
VALUES (
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '示範技師-林師傅',
    '0911222333',
    'test@lock-ai.com',
    '["Yale", "Chatlock", "美樂"]'::jsonb,
    '["新北市板橋區", "台北市信義區", "桃園市中壢區"]'::jsonb,
    4.7, 23, 'active',
    NOW() - INTERVAL '90 days',
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    capabilities = EXCLUDED.capabilities,
    service_regions = EXCLUDED.service_regions,
    rating = EXCLUDED.rating,
    completed_orders = EXCLUDED.completed_orders,
    status = EXCLUDED.status;

-- 3) 把 WO2（in_progress）指派給此技師（讓 dashboard online_count 反映 active+busy）
UPDATE work_orders
SET technician_id = '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    updated_at = NOW()
WHERE id = '55555555-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid;

-- 4) 額外 4 名展示用技師（無 user account；管理員列表/詳情用）。
--    密碼 hash 用 placeholder（password='disabled-not-loginable'），不會通過登入。
INSERT INTO users (id, tenant_id, email, password_hash, display_name, phone, role, is_active)
VALUES
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-chen@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '陳師傅', '0922334455', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-huang@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '黃師傅', '0933445566', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-wu@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '吳師傅', '0944556677', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-zhang@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '張師傅', '0955667788', 'technician', TRUE)
ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    display_name = EXCLUDED.display_name,
    phone = EXCLUDED.phone,
    is_active = EXCLUDED.is_active;

INSERT INTO technicians (
    id, tenant_id, user_id, name, phone, email,
    capabilities, service_regions,
    rating, completed_orders, status,
    created_at, updated_at
)
VALUES
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
     '陳師傅', '0922334455', 'tech-chen@example.com',
     '["Yale", "Mi-La"]'::jsonb,
     '["新北市新莊區", "新北市三重區"]'::jsonb,
     4.5, 47, 'active',
     NOW() - INTERVAL '120 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
     '黃師傅', '0933445566', 'tech-huang@example.com',
     '["Chatlock", "Dormakaba"]'::jsonb,
     '["台北市大安區", "台北市信義區", "台北市中山區"]'::jsonb,
     4.9, 89, 'active',
     NOW() - INTERVAL '60 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
     '吳師傅', '0944556677', 'tech-wu@example.com',
     '["美樂", "Yale"]'::jsonb,
     '["桃園市桃園區", "桃園市中壢區"]'::jsonb,
     4.2, 12, 'active',
     NOW() - INTERVAL '30 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid,
     '張師傅', '0955667788', 'tech-zhang@example.com',
     '["Chatlock", "Yale", "美樂", "Dormakaba"]'::jsonb,
     '["新北市板橋區", "新北市中和區", "新北市永和區"]'::jsonb,
     4.6, 65, 'active',
     NOW() - INTERVAL '180 days', NOW())
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    phone = EXCLUDED.phone,
    email = EXCLUDED.email,
    capabilities = EXCLUDED.capabilities,
    service_regions = EXCLUDED.service_regions,
    rating = EXCLUDED.rating,
    completed_orders = EXCLUDED.completed_orders,
    status = EXCLUDED.status;

COMMIT;

-- 驗證
SELECT t.id, t.name, t.email, t.status, t.rating, t.completed_orders,
       t.capabilities, t.service_regions
FROM technicians t
WHERE t.tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY t.created_at DESC;

SELECT wo.id, wo.status, wo.technician_id
FROM work_orders wo
WHERE wo.technician_id = '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid;
