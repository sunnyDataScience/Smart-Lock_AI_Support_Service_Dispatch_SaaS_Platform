-- ============================================================================
-- Migration 003 — Warranty 5-Mode 起算 (ADR-0044 v2 / FR-0015 / BR-WARRANTY-001..007)
-- ----------------------------------------------------------------------------
-- 對齊 frozen spec DDL: docs/architecture/data/ddl-migration-001-init.sql:223
--   saas.device_warranty
-- 本 repo 現行為 public schema（非 saas.）+ warranty_claims 表為實際 runtime 來源。
-- 本切片以「對 warranty_claims 加欄」對齊 spec 語意；獨立 device_warranty 表的
-- 整體遷移留待波次 P3（見 docs/_audit/spec-code-gap-audit-2026-06-01.md）。
--
-- warranty_start_mode 採 ADR-0044 v2 正典 6 值 enum（非舊版 purchase/handover/
-- activation/contract/manual_override）。
--
-- 非破壞：ALTER TABLE ADD COLUMN IF NOT EXISTS（可重跑）。forward-only。
-- 套用：psql "$POSTGRES_URI" -f SQL/migrations/003-warranty-5mode.sql
-- ============================================================================

-- 1. warranty_start_mode — 6 值 enum（ADR-0044 v2 正典）
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_start_mode TEXT NOT NULL DEFAULT 'purchase_date';

-- CHECK 約束以 DO block 確保可重跑（IF NOT EXISTS 對 constraint 無原生支援）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'warranty_start_mode_chk'
    ) THEN
        ALTER TABLE warranty_claims
            ADD CONSTRAINT warranty_start_mode_chk
            CHECK (warranty_start_mode IN (
                'purchase_date',
                'install_date',
                'handover_date',
                'brand_warranty_date',
                'contract_date',
                'manual_override'
            ));
    END IF;
END $$;

-- 2. warranty_period_months — default 24（品牌可 36/60）
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_period_months INT NOT NULL DEFAULT 24;

-- 3. warranty_period_months_override — B2B nullable，上限 60 個月（BR-WARRANTY-006）
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_period_months_override INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'warranty_override_cap_chk'
    ) THEN
        ALTER TABLE warranty_claims
            ADD CONSTRAINT warranty_override_cap_chk
            CHECK (warranty_period_months_override IS NULL
                   OR (warranty_period_months_override > 0
                       AND warranty_period_months_override <= 60));
    END IF;
END $$;

-- 4. warranty_scope — device / component（BR-WARRANTY 範圍）
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_scope TEXT NOT NULL DEFAULT 'device';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'warranty_scope_chk'
    ) THEN
        ALTER TABLE warranty_claims
            ADD CONSTRAINT warranty_scope_chk
            CHECK (warranty_scope IN ('device', 'component'));
    END IF;
END $$;

-- 5. warranty_inherit_from_site_group — 建商案件 default true（ADR-0044 §v2.5）
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_inherit_from_site_group BOOLEAN NOT NULL DEFAULT TRUE;

-- 6. B2B override audit 欄（BR-WARRANTY-006 — 主管核可 + audit trail）
--    ChangeRequest 串接標 TODO(P3)；本切片先存核可者 + 合約 doc id + 時間。
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_override_approved_by UUID;
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_override_contract_doc_id UUID;
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS warranty_override_approved_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN warranty_claims.warranty_start_mode IS
    'ADR-0044 v2 起算錨點：purchase_date / install_date / handover_date / brand_warranty_date / contract_date / manual_override';
COMMENT ON COLUMN warranty_claims.warranty_period_months IS
    '保固期（月）default 24；品牌可 36/60。warranty_end_date = warranty_start_date + period_months';
COMMENT ON COLUMN warranty_claims.warranty_period_months_override IS
    'B2B override（BR-WARRANTY-006）：nullable，上限 60 個月，需主管核可 + audit';
