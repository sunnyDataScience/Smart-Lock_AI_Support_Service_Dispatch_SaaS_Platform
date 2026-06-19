-- 064-tech-gis-performance.sql
-- WHY（CR-0061 / 審計 #10 #11 / BR-M06/BR-M07-03）：媒合 distance 為示意值非真實計算；排序只用單一
--   rating，未納 on-time/acceptance 多維績效。沿 mock-first 補技師座標 + 績效欄，媒合用 Haversine 真距離
--   + 多維績效進排序。（PostGIS 未裝，用純數學 Haversine + 區域中心點近似，不依賴 ST_Distance。）
-- WHAT：technicians +latitude/longitude/on_time_rate/acceptance_rate（nullable）+ seed active 技師 mock。
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS latitude        NUMERIC(9,6);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS longitude       NUMERIC(9,6);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS on_time_rate    NUMERIC(4,3);
ALTER TABLE technicians ADD COLUMN IF NOT EXISTS acceptance_rate NUMERIC(4,3);
COMMENT ON COLUMN technicians.latitude IS 'CR-0061 技師基地座標（mock；Haversine 媒合用）';
COMMENT ON COLUMN technicians.on_time_rate IS 'CR-0061 準時完工率 0-1（mock；多維績效排序）';

-- seed 示範（mock）：active 技師散佈大台北、績效 0.7-0.95 之間（用 id hash 散值，避免全同）
UPDATE technicians SET
  latitude  = 25.0 + (('x'||substr(md5(id::text),1,4))::bit(16)::int % 200) / 1000.0,
  longitude = 121.4 + (('x'||substr(md5(id::text),5,4))::bit(16)::int % 300) / 1000.0,
  on_time_rate    = 0.70 + (('x'||substr(md5(id::text),9,2))::bit(8)::int % 26) / 100.0,
  acceptance_rate = 0.70 + (('x'||substr(md5(id::text),11,2))::bit(8)::int % 26) / 100.0
WHERE status='active' AND latitude IS NULL;
