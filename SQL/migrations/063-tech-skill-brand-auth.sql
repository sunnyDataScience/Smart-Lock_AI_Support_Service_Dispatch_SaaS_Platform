-- 063-tech-skill-brand-auth.sql
-- migrate-targets: brand,tech  (LOCK-62：技師表在品牌庫與技師庫皆存在，兩庫皆須套用)
-- WHY（CR-0060 / 審計 #12 #13 / BR-M07-01 / BR-M06）：技師僅 capabilities JSONB 自由清單，無
--   結構化技能矩陣/等級、無品牌授權（媒合用 capabilities 充當）。spec 要技能矩陣(A/B/C 級) +
--   品牌授權(原廠認證)。沿會議「mock 先做可動態改」授權建資料模型 + seed 示範資料（is_mock）。
-- WHAT：兩新表 + seed（為現有 active 技師補示範技能/品牌授權）。idempotent。

CREATE TABLE IF NOT EXISTS technician_skill (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    technician_id   UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    skill_code      VARCHAR(60) NOT NULL,              -- 對齊 service_catalog category / 技能類
    level_id        VARCHAR(10) NOT NULL DEFAULT 'LV-B',  -- A/B/C（對齊 payout rule level）
    is_mock         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (technician_id, skill_code)
);
CREATE INDEX IF NOT EXISTS idx_tech_skill_tech ON technician_skill(technician_id);

CREATE TABLE IF NOT EXISTS technician_brand_authorization (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    technician_id   UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    brand           VARCHAR(100) NOT NULL,
    authorized      BOOLEAN NOT NULL DEFAULT TRUE,     -- 原廠認證/授權
    cert_expires_at DATE,                              -- 認證到期（NULL=無期限）
    is_mock         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (technician_id, brand)
);
CREATE INDEX IF NOT EXISTS idx_tech_brand_auth_tech ON technician_brand_authorization(technician_id);

-- seed（示範 mock）：現有 active 技師 → 通用技能 LV-B + 授權通用品牌（Generic/Yale/Philips/Samsung/Kaadas）
INSERT INTO technician_skill (technician_id, skill_code, level_id)
SELECT t.id, 'general_locksmith', 'LV-B' FROM technicians t WHERE t.status='active'
ON CONFLICT (technician_id, skill_code) DO NOTHING;
INSERT INTO technician_skill (technician_id, skill_code, level_id)
SELECT t.id, 'electronic_lock', 'LV-B' FROM technicians t WHERE t.status='active'
ON CONFLICT (technician_id, skill_code) DO NOTHING;

INSERT INTO technician_brand_authorization (technician_id, brand, authorized)
SELECT t.id, b.brand, TRUE
FROM technicians t
CROSS JOIN (VALUES ('Generic'),('Yale'),('Philips'),('Samsung'),('Kaadas')) AS b(brand)
WHERE t.status='active'
ON CONFLICT (technician_id, brand) DO NOTHING;
