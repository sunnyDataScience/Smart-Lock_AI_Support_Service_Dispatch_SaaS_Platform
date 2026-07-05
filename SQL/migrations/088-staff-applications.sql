-- ═══════════════════════════════════════════════════════════════════════════
-- 088-staff-applications.sql — 品牌員工帳號申請(CR-0114 R5)
--
-- 業主裁決 4:品牌站內登入頁註冊 tab 改「品牌員工帳號申請」——
--   對象是該品牌員工,自助申請後由品牌 Admin 審核並指派角色(UAT 版 7 角色
--   之 5 員工角色:admin/operations_manager/dispatcher/customer_service/reviewer)。
--
-- 設計:**不預建 users 列**(placeholder role 會漏進員工清單/角色統計,
--   且 CR-0090「依角色去重」對無角色列無法定義)。獨立申請表:
--     - 申請時即 bcrypt 密碼(核准直接搬進 users,免二次設密)
--     - 拒絕紀錄天然留審計
--     - 申請中/被拒者無 users 列 → 登入自然查無 → 不需動登入路徑
--
-- 慣例:IF NOT EXISTS,可重複套用。
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS staff_applications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    name             VARCHAR(100) NOT NULL,
    email            VARCHAR(255) NOT NULL,
    phone            VARCHAR(50),
    password_hash    TEXT NOT NULL,                    -- 申請時即 bcrypt
    status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','approved','rejected')),
    assigned_role    VARCHAR(50),                      -- 核准時指派(∈ 5 員工角色)
    created_user_id  UUID,                             -- 核准後建立的 users.id(審計串接)
    review_notes     TEXT,
    reviewed_by      UUID,                             -- 品牌 Admin user_id
    reviewed_at      TIMESTAMP WITH TIME ZONE,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 同租戶同 email 同時只能有一件待審申請(核准/拒絕後可再申請)
CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_app_pending_email
    ON staff_applications(tenant_id, email) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_staff_app_tenant_status
    ON staff_applications(tenant_id, status, created_at DESC);

COMMENT ON TABLE staff_applications IS '品牌員工帳號申請(CR-0114 R5);核准→建 users 並指派 5 員工角色之一,拒絕留審計';
