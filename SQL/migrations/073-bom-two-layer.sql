-- 073-bom-two-layer.sql
-- WHY（CR-0078 / TI-FIN-BOM-03 / BR-M10-01/02 / Q079-Q087）：兩層 BOM（成品 brand/model →
--   子件）+ material owner + 材料費歸屬 + 退回期限原無 substrate。Phase I（Manual First/Light，
--   mock-first 授權）先建資料模型，Phase II 接 part-level warranty 退回狀態機。
-- WHAT：saas.product_model（第一層 brand/model 主檔）+ saas.bom_line（第二層子件）。
--   material_owner enum 用 spec BR-M10-02（brand/company/locksmith/customer）；cost_attribution
--   用 Q087（customer/brand/technician/company）。material_ref 自由文字（指 inventory_item /
--   material_catalog，不硬 FK 避免綁定未定主檔）。return_deadline_days nullable（Phase II 預留）。
CREATE TABLE IF NOT EXISTS saas.product_model (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL,
    brand       TEXT NOT NULL,
    model       TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    is_mock     BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, brand, model)
);
CREATE TABLE IF NOT EXISTS saas.bom_line (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL,
    product_model_id    UUID NOT NULL REFERENCES saas.product_model(id) ON DELETE CASCADE,
    material_ref        TEXT NOT NULL,                 -- 指 inventory_item.part_number / material_catalog.material_code
    material_name       TEXT,
    quantity            NUMERIC(10,2) NOT NULL DEFAULT 1,
    material_owner      TEXT NOT NULL
                          CHECK (material_owner IN ('brand','company','locksmith','customer')),
    cost_attribution    TEXT NOT NULL
                          CHECK (cost_attribution IN ('customer','brand','technician','company')),
    return_deadline_days INT,                          -- NULL = 不需退回 / Phase II 補
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bom_line_model ON saas.bom_line (product_model_id);
CREATE INDEX IF NOT EXISTS idx_product_model_tenant ON saas.product_model (tenant_id, brand, model);
COMMENT ON TABLE saas.bom_line IS
  'CR-0078/TI-FIN-BOM-03：BOM 第二層子件 + material owner/cost_attribution/退回期限（Phase I mock）';
