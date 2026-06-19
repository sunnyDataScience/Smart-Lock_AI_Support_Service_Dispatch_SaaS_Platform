-- ============================================================================
-- Smart Lock AI Support & Service Dispatch SaaS Platform
-- Schema 擴充：媒體檔案上傳（T8 photos / 完工照片 / dispute evidence）
-- ============================================================================
--
-- 對應 endpoints：
--   POST   /api/v1/media                  上傳檔案
--   GET    /api/v1/media/{id}             下載檔案
--   GET    /api/v1/work-orders/{id}/media 列出某工單相關媒體
--
-- 儲存策略：
--   - MVP：本機檔案系統（路徑 = MEDIA_ROOT/{tenant_id}/{YYYY-MM}/{media_id}{ext}）
--   - 後續：可換 GCS/S3，service 層抽象 storage backend，DB 紀錄不變
--
-- Dependencies: Schema.sql 必須先執行
-- ============================================================================

CREATE TABLE IF NOT EXISTS media_files (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL,
    uploader_user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    work_order_id       UUID REFERENCES work_orders(id) ON DELETE SET NULL,
    dispute_id          UUID REFERENCES disputes(id) ON DELETE SET NULL,
    purpose             VARCHAR(40) NOT NULL CHECK (
                            purpose IN (
                                'door_check_before',
                                'door_check_after',
                                'completion_before',
                                'completion_during',  -- CR-0054 施工中拓孔結構照
                                'completion_after',
                                'dispute_evidence_customer',
                                'dispute_evidence_technician',
                                'other'
                            )
                        ),
    filename            VARCHAR(500) NOT NULL,
    content_type        VARCHAR(100) NOT NULL,
    size_bytes          INTEGER NOT NULL CHECK (size_bytes >= 0),
    storage_path        TEXT NOT NULL,          -- 相對 MEDIA_ROOT
    sha256              VARCHAR(64),            -- 完整 SHA-256 hash（小寫 hex）
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_files_wo
    ON media_files (work_order_id, purpose, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_files_dispute
    ON media_files (dispute_id, purpose, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_media_files_tenant
    ON media_files (tenant_id, created_at DESC);

COMMENT ON TABLE media_files IS
    '媒體檔案 metadata。實際檔案存於 MEDIA_ROOT/{storage_path}（MVP 本機 FS，後續可換 GCS/S3）';
COMMENT ON COLUMN media_files.purpose IS
    'T8 door check / completion 完工 / dispute evidence 三大用途分類';
COMMENT ON COLUMN media_files.storage_path IS
    '相對 MEDIA_ROOT 的路徑，例 00000000-.../2026-05/abc123.jpg';
