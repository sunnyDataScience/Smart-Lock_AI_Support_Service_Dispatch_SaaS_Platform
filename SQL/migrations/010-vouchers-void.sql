-- =============================================================================
-- 010-vouchers-void.sql
-- Track B S7 — Voucher Void v2（紅字沖銷 / ADR-VCH-001/002 / CR-0004 §8）
--
-- 決議（CR-0004 §8 HD-VCH-001~004）：
--   HD-VCH-001: saas.voucher 含 issuer_party / legal_basis / hash_prev / hash_self（hash 鏈）
--   HD-VCH-002: append-only——原傳票不 UPDATE；沖銷=新建反向分錄 + voucher_void_event
--   HD-VCH-003: keeperRole = platform admin JWT role（require_keeper_role dependency）
--   HD-VCH-004: schema 遷 saas（dual-write）；backfill from public.vouchers
--
-- 冪等：可重複執行。
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/010-vouchers-void.sql
-- =============================================================================

-- ── Step 1: saas.voucher（mirror public.vouchers + hash chain + reversal lineage）
CREATE TABLE IF NOT EXISTS saas.voucher (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES saas.tenant(id),
    voucher_no           text NOT NULL,
    period               text,
    related_entity_type  text,
    related_entity_id    uuid,
    debit_account        text,
    credit_account       text,
    amount               numeric(14,2) NOT NULL,
    currency             text NOT NULL DEFAULT 'TWD',
    posting_date         date,
    memo                 text,
    reason_code          text,
    reverses_voucher_id  uuid REFERENCES saas.voucher(id),
    issuer_party         text,
    legal_basis          text,
    hash_prev            text,
    hash_self            text,
    created_at           timestamptz NOT NULL DEFAULT now()
);

-- ── Step 2: UNIQUE (tenant_id, voucher_no)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'saas_voucher_tenant_voucher_no_key'
          AND conrelid = 'saas.voucher'::regclass
    ) THEN
        ALTER TABLE saas.voucher ADD CONSTRAINT saas_voucher_tenant_voucher_no_key
            UNIQUE (tenant_id, voucher_no);
    END IF;
END $$;

-- ── Step 3: index (tenant_id, created_at DESC)
CREATE INDEX IF NOT EXISTS idx_saas_voucher_tenant_created
    ON saas.voucher (tenant_id, created_at DESC);

-- ── Step 4: append-only trigger（HD-VCH-002 / BR-AUDIT-007）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'tg_saas_voucher_block_mutation'
          AND tgrelid = 'saas.voucher'::regclass
    ) THEN
        CREATE TRIGGER tg_saas_voucher_block_mutation
            BEFORE UPDATE OR DELETE ON saas.voucher
            FOR EACH ROW EXECUTE FUNCTION saas.tg_block_mutation();
    END IF;
END $$;

-- ── Step 5: saas.voucher_void_event（append-only 事件表）
CREATE TABLE IF NOT EXISTS saas.voucher_void_event (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES saas.tenant(id),
    voucher_id          uuid NOT NULL REFERENCES saas.voucher(id),
    reversal_voucher_id uuid NOT NULL REFERENCES saas.voucher(id),
    reason              text NOT NULL,
    comment             text,
    keeper_user_id      uuid NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- ── Step 6: UNIQUE (voucher_id) — 一張傳票只能被沖銷一次（重複 void → 409）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'saas_voucher_void_event_voucher_id_key'
          AND conrelid = 'saas.voucher_void_event'::regclass
    ) THEN
        ALTER TABLE saas.voucher_void_event ADD CONSTRAINT saas_voucher_void_event_voucher_id_key
            UNIQUE (voucher_id);
    END IF;
END $$;

-- ── Step 7: append-only trigger on voucher_void_event（BR-AUDIT-007）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'tg_saas_voucher_void_event_block_mutation'
          AND tgrelid = 'saas.voucher_void_event'::regclass
    ) THEN
        CREATE TRIGGER tg_saas_voucher_void_event_block_mutation
            BEFORE UPDATE OR DELETE ON saas.voucher_void_event
            FOR EACH ROW EXECUTE FUNCTION saas.tg_block_mutation();
    END IF;
END $$;

-- ── Step 8: Backfill public.vouchers → saas.voucher
--    voucher_number → voucher_no；period 由 posting_date 衍生；
--    reverses_voucher_id NULL；hash_self NULL（backfill）；
--    ON CONFLICT DO NOTHING（冪等）
INSERT INTO saas.voucher (
    id,
    tenant_id,
    voucher_no,
    period,
    related_entity_type,
    related_entity_id,
    debit_account,
    credit_account,
    amount,
    currency,
    posting_date,
    memo,
    created_at
)
SELECT
    v.id,
    v.tenant_id,
    v.voucher_number,
    CASE WHEN v.posting_date IS NOT NULL
         THEN to_char(v.posting_date, 'YYYY-MM')
         ELSE NULL
    END,
    v.related_entity_type,
    v.related_entity_id,
    v.debit_account,
    v.credit_account,
    v.amount,
    COALESCE(v.currency, 'TWD'),
    v.posting_date,
    v.memo,
    v.created_at
FROM public.vouchers v
WHERE v.tenant_id IS NOT NULL
ON CONFLICT (tenant_id, voucher_no) DO NOTHING;
