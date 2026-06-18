-- 041-quote-engine.sql
--
-- WHY（CR-0032 S2 / 20260617 gap-audit + ERP 藍圖 M04）：
--   CR-0027 只有 quote_line_items（work_order 層拆項），無報價主表/狀態機/核准/版本/凍結。
--   藍圖 M04：AI 可給 range 不可 final price；報價 gate = PC clear + evidence + customer confirm；
--   BR-M04-05 有效期 14d/3d。本 migration 建報價引擎 schema（Phase A）。
--
-- WHAT：
--   quote 主表（狀態機 + 版本鏈 + 有效期 + snapshot_hash 凍結欄）+ quote_line_items.quote_id（升為
--   quote 層，nullable 向後相容）+ quote_approval（核准軌跡）+ pricing_rule_snapshot（送客戶時凍結
--   價格規則，append-only）。數值/門檻走 esales mock 草稿（決議 5）；正式門檻待 esales Q-01~Q-12。
--
-- 影響：純新增表 + nullable 欄，idempotent。public schema（與 CR-0027 quote_line_items 一致）。

CREATE TABLE IF NOT EXISTS quote (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID REFERENCES work_orders(id) ON DELETE CASCADE,
    problem_card_id     UUID REFERENCES problem_cards(id) ON DELETE SET NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    state               VARCHAR(30) NOT NULL DEFAULT 'draft',
                        -- draft → pending_approval → approved → sent → accepted | rejected | expired | superseded
    total_amount        NUMERIC(12,2),                 -- 對外總額（Σ line customer_price）
    deposit_required    NUMERIC(12,2),                 -- 訂金（mock 草稿；正式規則 esales Q-08）
    expiry_at           TIMESTAMP WITH TIME ZONE,      -- BR-M04-05 14d/3d
    snapshot_hash       VARCHAR(64),                   -- 送客戶時凍結價格規則的 hash
    supersedes_quote_id UUID REFERENCES quote(id) ON DELETE SET NULL,  -- 版本鏈
    is_mock             BOOLEAN NOT NULL DEFAULT TRUE, -- 數值來自 mock 主檔
    tenant_id           UUID,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- quote_line_items 升為 quote 層（CR-0027 原為 work_order 層；保留 work_order_id 相容）
ALTER TABLE quote_line_items ADD COLUMN IF NOT EXISTS quote_id UUID REFERENCES quote(id) ON DELETE CASCADE;
ALTER TABLE quote_line_items ADD COLUMN IF NOT EXISTS service_code  VARCHAR(40);   -- 參照 service_catalog
ALTER TABLE quote_line_items ADD COLUMN IF NOT EXISTS material_code VARCHAR(40);   -- 參照 material_catalog

CREATE TABLE IF NOT EXISTS quote_approval (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id            UUID NOT NULL REFERENCES quote(id) ON DELETE CASCADE,
    approver_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    decision            VARCHAR(20) NOT NULL,          -- approved / rejected
    threshold_reason    TEXT,                          -- 為何需核准（金額/服務類別/折扣）
    comment             TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 送客戶當下凍結的價格規則（append-only，不可改；BR：報價快照不可變）
CREATE TABLE IF NOT EXISTS pricing_rule_snapshot (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id            UUID NOT NULL REFERENCES quote(id) ON DELETE CASCADE,
    rules_json          JSONB NOT NULL,                -- 凍結的服務/材料/加價規則快照
    hash                VARCHAR(64) NOT NULL,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quote_work_order ON quote (work_order_id);
CREATE INDEX IF NOT EXISTS idx_quote_state      ON quote (state);
CREATE INDEX IF NOT EXISTS idx_quote_line_quote ON quote_line_items (quote_id) WHERE quote_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quote_approval_q ON quote_approval (quote_id);
CREATE INDEX IF NOT EXISTS idx_pricing_snapshot_q ON pricing_rule_snapshot (quote_id);

COMMENT ON TABLE quote IS 'CR-0032 報價主表：狀態機 draft→pending_approval→approved→sent→accepted/rejected/expired/superseded；BR-M04-05 有效期；snapshot_hash 凍結';
COMMENT ON COLUMN quote.is_mock IS '數值來自 esales mock 主檔（CR-0034）；正式門檻待 esales Q-01~Q-12';
COMMENT ON TABLE pricing_rule_snapshot IS 'CR-0032 報價送客戶當下凍結的價格規則（append-only，報價快照不可變）';
