-- ============================================================================
-- Seed: Admin 登入帳號（前端 /login 唯一可用帳密）
-- ============================================================================
-- 必須在所有其他 seeds 之前執行（多份 seed 用 admin 當 reviewer/created_by）
--
-- Email:    test@lock-ai.com
-- Password: changeme123
-- bcrypt:   $2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6
-- Tenant:   00000000-0000-0000-0000-000000000001（系統預設租戶）
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
    'c782bcfe-89bb-40b3-94b3-8c73d7bd0961',
    '00000000-0000-0000-0000-000000000001',
    'test@lock-ai.com',
    '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
    '王小明',
    'admin',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- CR-0166 R1：第二位營運主管（SoD 雙簽 approver / 測試 secondary_admin_headers）。
-- M18 rollout 的 X-Approver 存在性驗證需其為真實 users 列（審計可追溯）。
INSERT INTO users (
    id, tenant_id, email, password_hash, display_name, role, is_active,
    created_at, updated_at
)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    '00000000-0000-0000-0000-000000000001',
    'ops-approver@lock-ai.com',
    '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
    '運營主管-審批',
    'operations_manager',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;
