-- ============================================================================
-- Seed: 後台角色示範帳號（CR-0021 — 5 角色 UI 隔離測試 / 會議決議 #9）
-- ============================================================================
-- 補齊 admin web 可登入的後台角色,讓 Iron 能以各角色點 UI 給反饋（Action #3）。
-- 既有：admin@example.com / dispatcher@example.com / demo-tech@example.com。
-- 本檔補：operations_manager / customer_service / reviewer。
--
-- Password: 全部 changeme123（demo 一致好記）
-- bcrypt:   $2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6
-- Tenant:   00000000-0000-0000-0000-000000000001
-- idempotent：ON CONFLICT (id) DO NOTHING
-- ============================================================================

INSERT INTO users (id, tenant_id, email, password_hash, display_name, role, is_active, created_at, updated_at)
VALUES
  ('0a000001-0000-4000-8000-000000000001',
   '00000000-0000-0000-0000-000000000001',
   'ops@example.com',
   '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
   '示範營運主管-林營運', 'operations_manager', TRUE, NOW(), NOW()),
  ('0a000002-0000-4000-8000-000000000002',
   '00000000-0000-0000-0000-000000000001',
   'cs@example.com',
   '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
   '示範客服-陳客服', 'customer_service', TRUE, NOW(), NOW()),
  ('0a000003-0000-4000-8000-000000000003',
   '00000000-0000-0000-0000-000000000001',
   'reviewer@example.com',
   '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
   '示範覆核-黃覆核', 'reviewer', TRUE, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;
