-- 098-pricing-snapshot-hashchain.sql — ADR-026 content-addressable 報價快照(CR-0149)
--
-- 稽核(2026-07-10)查實 ADR-026 Accepted 但 schema 零落地——現行仍為 041 舊制
-- (id PK + quote_id FK + rules_json + hash 欄,非定址、無 dedup、無 append-only
-- enforce)。業主裁決(CR-0149 §8,2026-07-10):
--   舊表更名 pricing_rule_snapshot_legacy 保留查證,新表全新開始;
--   存量 quote 豁免(FK NOT VALID,evidence 鏈自本日起算);purge 流程記遺留。
--
-- 新制:snapshot_hash=sha256(canonical payload) 為 PK(content-addressable、
-- insert 冪等 ON CONFLICT DO NOTHING);payload 含 tenant_id → 去重範圍=租戶內;
-- append-only 以 trigger enforce(ADR-026 明言非物理不可變;REVOKE 對表 owner
-- 無效,trigger 連 owner 一併擋)。quote.snapshot_hash 為 reference pointer
-- (業務 audit 與財務憑證分流,ADR-026)。
--
-- 影響:表更名+新表+trigger+FK(NOT VALID);idempotent。

-- 1. 舊制表更名保留(以 quote_id 欄存在與否判定舊形;冪等)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pricing_rule_snapshot'
      AND column_name = 'quote_id'
  ) THEN
    ALTER TABLE pricing_rule_snapshot RENAME TO pricing_rule_snapshot_legacy;
  END IF;
END $$;

-- 2. 新表(content-addressable)
CREATE TABLE IF NOT EXISTS pricing_rule_snapshot (
    snapshot_hash   TEXT PRIMARY KEY,             -- sha256(canonical payload,含 tenant_id)
    tenant_id       UUID NOT NULL,
    engine_type     TEXT NOT NULL,                -- 凍結當下引擎識別(quote_line_items_v1)
    version_id      TEXT,                         -- 引擎/規則版本(現階段可空,隨引擎版本化補)
    policy_hash     TEXT,                         -- discount_policy 子集之 sha256
    payload         JSONB NOT NULL,               -- 凍結之定價規則 payload(canonical)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prs_tenant_created
    ON pricing_rule_snapshot (tenant_id, created_at DESC);

-- 3. append-only enforce:UPDATE/DELETE 一律 RAISE(owner 亦擋)
CREATE OR REPLACE FUNCTION pricing_snapshot_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'pricing_rule_snapshot is append-only (ADR-026/CR-0149)';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pricing_snapshot_append_only ON pricing_rule_snapshot;
CREATE TRIGGER trg_pricing_snapshot_append_only
  BEFORE UPDATE OR DELETE ON pricing_rule_snapshot
  FOR EACH ROW EXECUTE FUNCTION pricing_snapshot_immutable();

-- 4. quote.snapshot_hash → FK reference pointer
--    NOT VALID:存量 quote 的 hash 屬 legacy 表不回填(業主裁決豁免);
--    新寫入(键值變更)照常檢查——送單流程先 INSERT 快照再 UPDATE quote。
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_quote_snapshot_hash'
  ) THEN
    ALTER TABLE quote
      ADD CONSTRAINT fk_quote_snapshot_hash
      FOREIGN KEY (snapshot_hash) REFERENCES pricing_rule_snapshot (snapshot_hash)
      NOT VALID;
  END IF;
END $$;
