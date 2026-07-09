-- ============================================================================
-- Seed: Dispatcher 示範帳號（V2.0 新獨立角色，解鎖 F-004 / F-019）
-- ⚠️ SA-06（2026-07-09）：dispatcher 已轉**保留角色**暫不開通（13_Security §3.1）——
--    不再出現在 _STAFF_ROLES / 前端開通選項；本 seed 保留＝存量帳號 fixture
--    （conftest dispatcher_headers 與角色隔離測試依賴），代表既有帳號仍可登入運作。
-- ============================================================================
-- 必須在 _admin_user.sql 之後執行（沿用同一 default tenant）。
--
-- Email:    dispatcher@example.com
-- Password: changeme123
-- bcrypt:   $2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6
-- Tenant:   00000000-0000-0000-0000-000000000001（系統預設租戶）
-- Role:     dispatcher（PM 拍板 Q1=A — 獨立角色，非 customer_service 子權限）
--
-- idempotent：ON CONFLICT (id) DO NOTHING
-- ============================================================================

INSERT INTO users (
    id,
    tenant_id,
    email,
    password_hash,
    display_name,
    role,
    is_active,
    created_at,
    updated_at
)
VALUES (
    'd1893a7f-1c2e-4a6b-9e4d-2f5b8c6a1e02',
    '00000000-0000-0000-0000-000000000001',
    'dispatcher@example.com',
    '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
    '示範派工員-王派工',
    'dispatcher',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;
