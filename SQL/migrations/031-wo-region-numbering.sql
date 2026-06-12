-- 031-wo-region-numbering.sql
-- CR-0020：公單 ID 改 {2碼地區}-{6碼流水}（如 TP-000001），per-region 原子流水，
-- 工單建立時依 customer_address 發號。決策見 docs/4-exploration/CR-0020 §8 + ADR-0110。
-- 地區前綴「僅用工單」（Q6）;RM/WC/SOP 維持既有類型前綴 generate_doc_number。

-- ── 1. per-region 流水計數表 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wo_region_counter (
    region      TEXT PRIMARY KEY,
    last_serial BIGINT NOT NULL DEFAULT 0
);

-- ── 2. 地址 → 2 碼地區碼（縣市對應；解析不到 → ZZ）────────────────────────
-- 台/臺 異體字皆對應同碼。NT=新北、NA=南投（避免衝突）;HC=新竹市、HD=新竹縣。
CREATE OR REPLACE FUNCTION wo_region_code(addr TEXT)
RETURNS TEXT AS $$
DECLARE
    city TEXT;
BEGIN
    IF addr IS NULL OR btrim(addr) = '' THEN
        RETURN 'ZZ';
    END IF;
    city := substring(btrim(addr) from '^(.+?[市縣])');
    RETURN CASE city
        WHEN '台北市' THEN 'TP' WHEN '臺北市' THEN 'TP'
        WHEN '新北市' THEN 'NT'
        WHEN '桃園市' THEN 'TY'
        WHEN '台中市' THEN 'TC' WHEN '臺中市' THEN 'TC'
        WHEN '台南市' THEN 'TN' WHEN '臺南市' THEN 'TN'
        WHEN '高雄市' THEN 'KH'
        WHEN '基隆市' THEN 'KL'
        WHEN '新竹市' THEN 'HC' WHEN '新竹縣' THEN 'HD'
        WHEN '苗栗縣' THEN 'ML'
        WHEN '彰化縣' THEN 'CH'
        WHEN '南投縣' THEN 'NA'
        WHEN '雲林縣' THEN 'YL'
        WHEN '嘉義市' THEN 'CY' WHEN '嘉義縣' THEN 'CT'
        WHEN '屏東縣' THEN 'PT'
        WHEN '宜蘭縣' THEN 'IL'
        WHEN '花蓮縣' THEN 'HL'
        WHEN '台東縣' THEN 'TT' WHEN '臺東縣' THEN 'TT'
        WHEN '澎湖縣' THEN 'PH'
        WHEN '金門縣' THEN 'KM'
        WHEN '連江縣' THEN 'LC'
        ELSE 'ZZ'
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ── 3. 依地址原子發 per-region 流水號 → 'TP-000001' ────────────────────────
CREATE OR REPLACE FUNCTION generate_wo_number(addr TEXT)
RETURNS TEXT AS $$
DECLARE
    v_region TEXT := wo_region_code(addr);
    v_serial BIGINT;
BEGIN
    INSERT INTO wo_region_counter (region, last_serial)
    VALUES (v_region, 1)
    ON CONFLICT (region) DO UPDATE
        SET last_serial = wo_region_counter.last_serial + 1
    RETURNING last_serial INTO v_serial;
    RETURN v_region || '-' || LPAD(v_serial::TEXT, 6, '0');
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_wo_number(TEXT) IS
'CR-0020: 公單號 {2碼地區}-{6碼流水}, per-region 原子遞增。地區前綴僅用工單。';
