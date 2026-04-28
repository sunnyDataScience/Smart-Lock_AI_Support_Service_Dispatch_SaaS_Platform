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
--   - GET /technicians/me（需登入 demo-tech@example.com / techpass123）→ 200
--   - dashboard.technicians = { total_count: 1, online_count: 0, dispatchable_count: 0 }
--     （技師雖 active，但有 in_progress 工單，故 online_count = 0；待 WO2 結案後重算為 1）
-- ============================================================================

BEGIN;

-- 1) demo 技師對應的 user 帳號（role='technician'）
-- password = techpass123（bcrypt $2b$12$...）
INSERT INTO users (
    id, tenant_id, email, password_hash, display_name, phone, role, is_active
)
VALUES (
    '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-tech@example.com',
    '$2b$12$j8386WAs/k1Tb/tx3PFiq.wR3ba9A3JafXEo3MTaiCpU/f.pfl08q',
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
    'demo-tech@example.com',
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
