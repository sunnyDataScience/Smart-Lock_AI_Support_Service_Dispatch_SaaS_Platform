-- ═══════════════════════════════════════════════════════════════════════════
-- zz_technician_skills.sql — 技師技能矩陣 + 品牌授權 seed（CR-0137 / SIT 修）
--
-- 修 seed 順序 bug（M1 SIT 抓到，CR-0137）：migration 063 的資料 seed 依
-- 「technicians WHERE status='active'」插技能/授權，但 technicians 於**所有
-- migration 之後**才由 SQL/seeds/technicians.sql 建立 → 063 執行時無技師 →
-- 0 筆 skill/auth（test_cr_0060 / test_cr_0114 恆 fail）。
--
-- 本檔名 `zz_` 前綴確保於 seed glob 排序**最後**（在 technicians.sql 之後），
-- 補跑同一份 seed 邏輯（063 的 INSERT...SELECT，idempotent ON CONFLICT）。
-- 落庫：品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO technician_skill (technician_id, skill_code, level_id)
SELECT t.id, 'general_locksmith', 'LV-B' FROM technicians t WHERE t.status = 'active'
ON CONFLICT (technician_id, skill_code) DO NOTHING;

INSERT INTO technician_skill (technician_id, skill_code, level_id)
SELECT t.id, 'electronic_lock', 'LV-B' FROM technicians t WHERE t.status = 'active'
ON CONFLICT (technician_id, skill_code) DO NOTHING;

INSERT INTO technician_brand_authorization (technician_id, brand, authorized)
SELECT t.id, b.brand, TRUE
FROM technicians t
CROSS JOIN (VALUES ('Generic'), ('Yale'), ('Philips'), ('Samsung'), ('Kaadas')) AS b(brand)
WHERE t.status = 'active'
ON CONFLICT (technician_id, brand) DO NOTHING;
