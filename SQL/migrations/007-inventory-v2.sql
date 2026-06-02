-- ============================================================================
-- Migration 007 — Inventory v2 per-tenant 庫存狀態機（Track B S3 / FR-0007 / CR-0004 §8）
-- ----------------------------------------------------------------------------
-- 2 tables: saas.inventory_item, saas.inventory_transaction
-- per-tenant 獨立倉庫（HD-INV-01）：每個 tenant 擁有自己的庫存品項
-- owner enum（ADR-0052）：platform / brand / locksmith
-- serial_required（ADR-0053）：主鎖+高價零件強制、低價選填
--
-- Assumptions:
--   - saas schema 已存在（migration 004 建立）
--   - saas.tenant 已存在（migration 004 建立；dev seed 00000000-…-0001 存在）
--   - public.inventory_items 完全保留（dual-mount 過渡；不動 legacy）
--   - public.inventory_transactions 完全保留（不動 legacy）
--
-- Backfill:
--   public.inventory_items → saas.inventory_item
--     tenant_id 指派給 dev tenant 00000000-…-0001（legacy 無 tenant_id）
--     owner 預設 'platform'、serial_required 預設 false
--     idempotent (ON CONFLICT (tenant_id, part_number) DO NOTHING)
--   public.inventory_transactions → saas.inventory_transaction
--     tenant_id 由 JOIN saas.inventory_item 取得
--     transaction_type 映射：'purchase'/'consume'/'return'/'adjust' 同名直帶
--       legacy 未知 type → 'adjust'
--     idempotent (ON CONFLICT (id) DO NOTHING)
--
-- 注意：
--   - brand_compatibility: legacy 是 jsonb，v2 用 text[]；backfill 時 jsonb → text[]
--     （若 legacy 是 JSON array of strings，直接轉；否則 skip / 留空）
--   - unit_cost: legacy 是 double precision，v2 是 numeric(12,2)；CAST 對齊
--   - consume 必須走 SELECT FOR UPDATE transaction（service 層強制，DB 層不另加 trigger）
--
-- ADR-0052 status 不一致注意：frontmatter accepted，body ## Status: Draft；
--   業主授權按 Decision(推薦) 值開發：owner enum = platform/brand/locksmith。
--
-- HD-INV-03 serial 擋 WO complete：本波次不改 work_order_service；
--   serial_required=true 且缺 serial → 422 於 :consume 端點；
--   WO complete gate 留 follow-up CR。
--
-- Apply: psql "$POSTGRES_URI" -f SQL/migrations/007-inventory-v2.sql
-- Idempotent: CREATE TABLE IF NOT EXISTS / indexes IF NOT EXISTS / ON CONFLICT DO NOTHING
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. saas.inventory_item
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.inventory_item (
  id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid          NOT NULL REFERENCES saas.tenant(id),
  part_number          text          NOT NULL,
  name                 text          NOT NULL,
  category             text,
  -- brand_compatibility: text[] 對齊 legacy jsonb（backfill 時 JSON array → text[]）
  brand_compatibility  text[],
  -- unit_cost: numeric(12,2) 對齊 legacy double precision（backfill 時 CAST）
  unit_cost            numeric(12,2),
  quantity_on_hand     int           NOT NULL DEFAULT 0
                                     CHECK (quantity_on_hand >= 0),
  reorder_point        int           NOT NULL DEFAULT 0,
  supplier             text,
  -- ADR-0052：owner enum = platform / brand / locksmith
  owner                text          NOT NULL DEFAULT 'platform'
                                     CHECK (owner IN ('platform', 'brand', 'locksmith')),
  -- ADR-0053：主鎖+高價零件(>NTD 1,000) 強制 serial，低價選填
  serial_required      boolean       NOT NULL DEFAULT false,
  is_active            boolean       NOT NULL DEFAULT true,
  created_at           timestamptz   NOT NULL DEFAULT now(),
  updated_at           timestamptz   NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, part_number)
);

-- 複合 index：tenant 過濾 + is_active + 倒序分頁
CREATE INDEX IF NOT EXISTS inventory_item_tenant_active_created_idx
  ON saas.inventory_item(tenant_id, is_active, created_at DESC);

COMMENT ON TABLE saas.inventory_item IS
  'v2 per-tenant 庫存品項（FR-0007 / CR-0004 §8 HD-INV-01）; '
  'ADR-0052: owner enum=platform/brand/locksmith; '
  'ADR-0053: serial_required=true → consume 時未帶 serial → 422; '
  'HD-INV-03: serial 擋 WO complete 留 follow-up。';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. saas.inventory_item updated_at 自動更新 trigger（仿 migration 006 格式）
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION saas.inventory_item_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'tg_inventory_item_updated_at'
      AND tgrelid = 'saas.inventory_item'::regclass
  ) THEN
    CREATE TRIGGER tg_inventory_item_updated_at
      BEFORE UPDATE ON saas.inventory_item
      FOR EACH ROW EXECUTE FUNCTION saas.inventory_item_set_updated_at();
  END IF;
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. saas.inventory_transaction（ledger，append-style）
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.inventory_transaction (
  id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid         NOT NULL REFERENCES saas.tenant(id),
  item_id          uuid         NOT NULL REFERENCES saas.inventory_item(id),
  -- transaction_type：purchase/consume/return/adjust
  -- 方向語意：consume 減、purchase/return 加、adjust 可正可負（quantity 欄存正數，方向由 type 決定）
  transaction_type text         NOT NULL
                                CHECK (transaction_type IN ('purchase', 'consume', 'return', 'adjust')),
  -- quantity 恆為正數；consume service 層負責扣減 quantity_on_hand
  quantity         int          NOT NULL CHECK (quantity > 0),
  work_order_id    uuid,
  technician_id    uuid,
  -- serial：ADR-0053，serial_required=true 時 consume 必須帶此欄
  serial           text,
  notes            text,
  created_at       timestamptz  NOT NULL DEFAULT now()
);

-- 複合 index：tenant + item 倒序分頁
CREATE INDEX IF NOT EXISTS inventory_transaction_tenant_item_created_idx
  ON saas.inventory_transaction(tenant_id, item_id, created_at DESC);

COMMENT ON TABLE saas.inventory_transaction IS
  'v2 庫存異動 ledger（FR-0007 / CR-0004 §8）; '
  'append-only；consume 需在 transaction + FOR UPDATE 中執行（AC-05 並發保護）; '
  'quantity 恆正；方向由 transaction_type 決定（consume→扣、purchase/return→加）。';

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Backfill: public.inventory_items → saas.inventory_item
--    tenant_id 指派給 dev tenant 00000000-…-0001（legacy 無 tenant_id）
--    brand_compatibility: legacy jsonb → text[]（嘗試 jsonb → text array）
--    unit_cost: double precision → numeric(12,2)
--    idempotent via ON CONFLICT (tenant_id, part_number) DO NOTHING
--    注意：live DB 目前 0 rows，backfill 為安全兜底
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO saas.inventory_item (
  id,
  tenant_id,
  part_number,
  name,
  category,
  brand_compatibility,
  unit_cost,
  quantity_on_hand,
  reorder_point,
  supplier,
  owner,
  serial_required,
  is_active,
  created_at,
  updated_at
)
SELECT
  i.id,
  '00000000-0000-0000-0000-000000000001'::uuid,  -- dev tenant
  i.part_number,
  i.name,
  i.category,
  -- jsonb → text[]：若為 JSON array，展開為 text array；否則留空
  CASE
    WHEN i.brand_compatibility IS NOT NULL
         AND jsonb_typeof(i.brand_compatibility) = 'array'
    THEN ARRAY(
      SELECT jsonb_array_elements_text(i.brand_compatibility)
    )
    ELSE NULL
  END,
  CAST(i.unit_cost AS numeric(12,2)),
  COALESCE(i.quantity_on_hand, 0),
  COALESCE(i.reorder_point, 0),
  i.supplier,
  'platform',   -- 預設 owner
  false,        -- 預設 serial_required
  COALESCE(i.is_active, true),
  COALESCE(i.created_at, NOW()),
  COALESCE(i.updated_at, NOW())
FROM public.inventory_items i
ON CONFLICT (tenant_id, part_number) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Backfill: public.inventory_transactions → saas.inventory_transaction
--    tenant_id 由 JOIN saas.inventory_item 取得（item 已由上方 backfill 建立）
--    transaction_type 映射：'purchase'/'consume'/'return'/'adjust' 同名；其餘 → 'adjust'
--    idempotent via ON CONFLICT (id) DO NOTHING
--    注意：live DB 目前 0 rows，backfill 為安全兜底
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO saas.inventory_transaction (
  id,
  tenant_id,
  item_id,
  transaction_type,
  quantity,
  work_order_id,
  technician_id,
  notes,
  created_at
)
SELECT
  t.id,
  si.tenant_id,
  t.item_id,
  -- transaction_type 映射
  CASE t.transaction_type
    WHEN 'purchase' THEN 'purchase'
    WHEN 'consume'  THEN 'consume'
    WHEN 'return'   THEN 'return'
    WHEN 'adjust'   THEN 'adjust'
    ELSE 'adjust'
  END,
  -- quantity 須正數：abs(quantity) 取絕對值（legacy 可能有負值）
  GREATEST(ABS(COALESCE(t.quantity, 1)), 1),
  t.work_order_id,
  t.technician_id,
  t.notes,
  COALESCE(t.created_at, NOW())
FROM public.inventory_transactions t
JOIN saas.inventory_item si ON si.id = t.item_id
ON CONFLICT (id) DO NOTHING;
