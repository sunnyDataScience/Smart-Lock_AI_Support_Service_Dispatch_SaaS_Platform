-- ============================================================================
-- Migration 016 — SOP v2 list expand（CR-0006 / ADR-0104 / FR-SOP-001~002）
-- ----------------------------------------------------------------------------
-- 業主 2026-06-04 拍 CR-0006 §8 全 5 HD：
--   HD-01 = (a) 響應 shape 與 KB 一致（meta-wrap，由 sops_v2 程式碼處理）
--   HD-02 = (a) sop_drafts DELETE 軟刪（加 deleted_at）
--   HD-03 = (a) audit log 共用 saas.kb_audit_log（doc_type CHECK 擴 'sop'）
--   HD-04 = (a) POST /sops/family-reviews 路由廢棄（不在本 migration scope）
--   HD-05 = (a) SLA pending 視圖即時查（無 cache schema 變動）
--
-- 本 migration 對應 HD-02 + HD-03：DDL 變動。
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/016-sop-v2-list-expand.sql
-- Idempotent: ALTER TABLE ADD COLUMN IF NOT EXISTS + DROP CONSTRAINT IF EXISTS
--             + ADD CONSTRAINT
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. sop_drafts 加 deleted_at（HD-02 軟刪）
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE sop_drafts
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_sop_drafts_active
    ON sop_drafts(tenant_id, created_at DESC)
    WHERE deleted_at IS NULL;     -- GET list 預設過濾

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. kb_audit_log doc_type CHECK 擴 'sop'（HD-03 共用 schema）
--    既有 CHECK (doc_type IN ('case', 'manual')) → 改為 IN ('case', 'manual', 'sop')
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
    -- 找到既有 CHECK constraint 名稱（migration 015 未顯式命名，PG 自動產生）
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'saas.kb_audit_log'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%doc_type%case%manual%'
          AND pg_get_constraintdef(oid) NOT LIKE '%sop%'
    ) THEN
        -- 找到舊 constraint 並 drop
        EXECUTE (
            SELECT 'ALTER TABLE saas.kb_audit_log DROP CONSTRAINT ' || conname
            FROM pg_constraint
            WHERE conrelid = 'saas.kb_audit_log'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%doc_type%case%manual%'
              AND pg_get_constraintdef(oid) NOT LIKE '%sop%'
            LIMIT 1
        );
    END IF;
END $$;

-- 重新 ADD 包含 'sop' 的 CHECK constraint（顯式命名，避免下次再要猜）
--
-- ⚠️ 這句必須先 DROP IF EXISTS：上面 DO 區塊的守衛帶 `NOT LIKE '%sop%'`，
--    本檔套用過一次後新約束已含 'sop'，守衛就再也匹配不到、不會 drop，
--    於是這句無守衛的 ADD 會炸 "constraint ... already exists"。
--    2026-07-28 實測：對已套用的品牌庫重跑 apply-schema-routed.sh 即在此中斷。
ALTER TABLE saas.kb_audit_log
    DROP CONSTRAINT IF EXISTS kb_audit_log_doc_type_check;

ALTER TABLE saas.kb_audit_log
    ADD CONSTRAINT kb_audit_log_doc_type_check
    CHECK (doc_type IN ('case', 'manual', 'sop'));

-- ============================================================================
-- 註記：HD-04 POST /sops/family-reviews 路由廢棄
--   不需 schema 變動。Router 層 sops_v2.py 已有 /sops/{id}/review/family；
--   legacy family_reviews.py:64 POST 路徑由本 CR 不引用，P4 cutover 統一刪。
-- ============================================================================

-- ============================================================================
-- 註記：HD-05 SLA pending 視圖即時查
--   不需 schema 變動。GET /tenants/{tid}/sops/family-reviews:pending 由
--   service 層 SELECT family_reviews WHERE status='pending' + sla_deadline 條件，
--   每次請求即時計算；無 cache 表或 materialized view。
-- ============================================================================
