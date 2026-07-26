-- ═══════════════════════════════════════════════════════════════════════════
-- migrate-targets: brand,tech  (LOCK-62：技師表在品牌庫與技師庫皆存在，兩庫皆須套用)
-- 090-technician-registration-documents.sql — 師傅 KYC 文件上傳(CR-0115 S-upload)
--
-- 業主裁決(CR-0115 §8-2):(a) 兩階段 —— 先送基本資料建 pending 帳號 → 回
-- 一次性 upload token → 憑 token 上傳文件(身分證正反面/證照掃描/保險證明或
-- 良民證)。§8-7:檔案落本機 MEDIA_ROOT(kyc-registration/ 子樹,與 tenant
-- media 隔離);GCS private bucket + signed URL 另 CR。
--
-- 設計:
--   - token 明文不落庫,只存 SHA-256(token_hash);48h 過期 + 次數上限,
--     師傅離開 pending_approval 後即不可再用(service 層檢查)。
--   - 文件 metadata 存本表(不用品牌庫 media_files —— KYC 屬師傅身分域,
--     §8-1 最小揭露不落品牌庫);檔案實體在共用 media volume 的 kyc-registration/。
--
-- 慣例:IF NOT EXISTS,可重複套用。
-- 落庫:師傅身分權威庫(tech-db,lock_tech);fallback 單庫時即主庫。
-- ═══════════════════════════════════════════════════════════════════════════

-- ── 兩階段上傳 token(§8-2a)────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS technician_upload_token (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technician_id UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    token_hash    VARCHAR(64) NOT NULL UNIQUE,   -- SHA-256 hex(明文不落庫)
    expires_at    TIMESTAMPTZ NOT NULL,
    upload_count  INTEGER NOT NULL DEFAULT 0,
    max_uploads   INTEGER NOT NULL DEFAULT 12,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tech_upload_token_tech
    ON technician_upload_token (technician_id);

-- ── 註冊文件 metadata(Tier 3)─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS technician_registration_document (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technician_id UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    tenant_id     UUID NOT NULL,
    doc_type      VARCHAR(30) NOT NULL,   -- id_front / id_back / license / insurance
    filename      VARCHAR(500),
    content_type  VARCHAR(100) NOT NULL,
    size_bytes    INTEGER NOT NULL,
    storage_path  TEXT NOT NULL,          -- 相對 MEDIA_ROOT(kyc-registration/{tech_id}/…)
    sha256        VARCHAR(64) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tech_reg_doc_tech
    ON technician_registration_document (technician_id);

-- ── lifecycle audit 追加 kyc_reveal 事件型別(§8-3 揭露稽核)────────────────
--  平台管理員檢視敏感 PII 全值時寫入(非狀態轉移,previous/new_status 皆 null)。
--  不用品牌庫 audit_events:其 actor_id FK 指品牌庫 users,平台管理員帳號在
--  平台庫會 FK violation;且平台層稽核不應落在單一品牌庫。
ALTER TABLE saas.technician_lifecycle_event
    DROP CONSTRAINT IF EXISTS technician_lifecycle_event_event_type_check;
ALTER TABLE saas.technician_lifecycle_event
    ADD CONSTRAINT technician_lifecycle_event_event_type_check CHECK (
        event_type = ANY (ARRAY[
            'onboarding_approved'::text, 'onboarding_rejected'::text,
            'suspended'::text, 'reactivated'::text, 'terminated'::text,
            'rating_threshold_breach'::text, 'cert_expired'::text,
            'kyc_reveal'::text
        ])
    );
