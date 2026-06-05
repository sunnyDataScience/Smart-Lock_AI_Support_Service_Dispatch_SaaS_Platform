-- ============================================================================
-- 017-reconciliation-exceptions.sql — CR-0018 Stage 1: Flow 13 EX5
-- ============================================================================
-- 目的：對帳異常 (Reconciliation Exception) 獨立表 + 六態狀態機 + 三路徑修正
--      + SoD 雙簽（對齊 saas.reconciliation）。
--
-- HD 決議：
--   HD-1 = (a) 新表 saas.reconciliation_exception（不污染 disputes）
--   HD-2 = (b) 六態 detected → ops_review → fix_proposed → fix_approved
--                  → applied → closed
--   HD-3 = (c) 補單/註銷走本服務 endpoint；衝銷 fix_path 連動 voucher_void
--   HD-4 = (a) 雙簽（proposed_by + approved_by，CHECK 相異）
--   HD-5 = (c) 雙保險：upload-time 即時偵測 + cron daily 兜底
--             （本 migration 只落 schema 與 detected_by 欄位，偵測器
--              在 reconciliation upload service / cron 各自呼叫
--              reconciliation_exception_service.detect_*）
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.reconciliation_exception (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  reconciliation_id   uuid        NOT NULL REFERENCES saas.reconciliation(id),

  -- 例外類型
  exception_kind      text        NOT NULL CHECK (exception_kind IN (
    'amount_mismatch',    -- 金額不符
    'missing_invoice',    -- 缺發票
    'duplicate_entry',    -- 重複入帳
    'orphan_settlement',  -- 孤兒結算（settlement 找不到對應 reconciliation row）
    'other'
  )),

  -- 六態狀態機 HD-2 (b)
  status              text        NOT NULL DEFAULT 'detected' CHECK (status IN (
    'detected',           -- 偵測到（系統寫入）
    'ops_review',         -- ops 介入分析
    'fix_proposed',       -- 修正方案已提（CSM 雙簽 step-1）
    'fix_approved',       -- 修正方案核准（ops_manager 雙簽 step-2）
    'applied',            -- 修正已套用（補單/註銷/衝銷完成）
    'closed'              -- 結案
  )),

  -- 三修正路徑 HD-3
  fix_path            text        NULL CHECK (fix_path IS NULL OR fix_path IN (
    'invoice_supplement', -- 路徑 1：補單
    'recon_void',         -- 路徑 2：註銷對帳列
    'voucher_reverse'     -- 路徑 3：衝銷（走 voucher_void）
  )),

  -- 偵測資訊
  detected_by         text        NOT NULL CHECK (detected_by IN (
    'upload_realtime',    -- HD-5 (a) 對帳檔上傳當下即時偵測
    'cron_daily',         -- HD-5 (b) 每日 02:00 cron 兜底
    'manual'              -- ops 手動補建
  )),
  detected_at         timestamptz NOT NULL DEFAULT NOW(),
  amount_delta        numeric(12,2) NULL,        -- 金額差（正/負）；amount_mismatch 必填
  description         text        NOT NULL,

  -- 雙簽 HD-4 (a) — 對齊 saas.reconciliation pattern
  proposed_by         uuid        NULL,           -- CSM 提案
  proposed_at         timestamptz NULL,
  approved_by         uuid        NULL,           -- ops_manager 核准
  approved_at         timestamptz NULL,

  -- 連動：路徑 1 補單 / 路徑 3 衝銷 留 reference id
  applied_voucher_id  uuid        NULL,           -- 路徑 3：對應 vouchers.id
  applied_invoice_id  uuid        NULL,           -- 路徑 1：對應 invoices.id（補的發票）
  resolution_note     text        NULL,

  created_at          timestamptz NOT NULL DEFAULT NOW(),
  updated_at          timestamptz NOT NULL DEFAULT NOW(),

  -- DB 層 SoD backstop：與 reconciliation 一致
  CONSTRAINT exc_dual_sign_distinct
    CHECK (proposed_by IS NULL OR approved_by IS NULL OR proposed_by <> approved_by)
);

CREATE INDEX IF NOT EXISTS exc_tenant_status_created_idx
  ON saas.reconciliation_exception(tenant_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS exc_recon_idx
  ON saas.reconciliation_exception(reconciliation_id);

-- 開放例外列表（給 ops dashboard）：未結案的 row only
CREATE INDEX IF NOT EXISTS exc_open_detected_idx
  ON saas.reconciliation_exception(detected_at DESC)
  WHERE status NOT IN ('closed');

COMMENT ON TABLE saas.reconciliation_exception IS
  'CR-0018 Flow 13 EX5 對帳異常表（dual-sign）；六態狀態機；'
  '三路徑修正：補單/註銷/衝銷（衝銷連動 voucher_void）';

COMMENT ON COLUMN saas.reconciliation_exception.fix_path IS
  'NULL 表示尚未決定路徑（status=detected/ops_review）；'
  '走衝銷時 applied_voucher_id 必填，補單時 applied_invoice_id 必填';

COMMENT ON COLUMN saas.reconciliation_exception.detected_by IS
  'upload_realtime: reconciliation upload service 即時偵測；'
  'cron_daily: cron daily 02:00 兜底；'
  'manual: ops 手動補建（罕見）';
