-- ============================================================================
-- Seed（技師權威庫 lock_tech 專用）：5 名 seed 技師身分 — CR-0165 SEED-1
-- ============================================================================
-- WHY：品牌庫 seed（SQL/seeds/technicians.sql）只灌品牌庫；權威庫唯一 bootstrap
--   是 split-tech-db.sh 初次全量拷貝＋「非空即跳過」冪等 → 品牌庫重灌 seed 後
--   權威庫不再同步，漂移必然再現（UAT SEED-1）。投影-only 技師一旦觸發鏡射，
--   tech_mirror 對權威庫查無的 id 會 DELETE 品牌投影列＋technicians FK CASCADE
--   連鎖刪光品牌側身分資料（UAT F9「登入即刪技師資料」根源）。
--
-- 套用：split-tech-db.sh 於拆分後自動套用（fresh 與 skip 兩路徑皆套，冪等）；
--   手動：docker exec -i lock-tech-tech-db-1 psql -U lock -d lock_tech < 本檔
-- ⚠️ 本檔僅落技師權威庫；不得加入品牌庫 db-init 的 SEED_ORDER。
--
-- 密碼（CR-0165 §8-6 裁決）：4 名展示技師＝disabled 佔位 hash（不可登入，
--   與品牌 seed 同慣例）；test@lock-ai.com＝changeme123（登入示範帳號）。
-- ON CONFLICT DO NOTHING：權威庫既有列（如初次拆分拷貝、真實註冊）一律不覆蓋。
-- ============================================================================

BEGIN;

-- 1) users（技師權威庫只有技師列；憑證以本庫為權威——CR-0164 B）
INSERT INTO users (id, tenant_id, email, password_hash, display_name, phone, role, is_active)
VALUES
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'test@lock-ai.com', '$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6',
     '示範技師-林師傅', '0911222333', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-chen@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '陳師傅', '0922334455', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-huang@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '黃師傅', '0933445566', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-wu@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '吳師傅', '0944556677', 'technician', TRUE),
    ('66666666-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     'tech-zhang@example.com', '$2b$12$disabled.not.loginable.placeholder.hash.value.no.login',
     '張師傅', '0955667788', 'technician', TRUE)
ON CONFLICT (id) DO NOTHING;

-- 2) technicians（與品牌庫 seed 同 UUID——投影/權威同 id 是鏡射前提）
INSERT INTO technicians (
    id, tenant_id, user_id, name, phone, email,
    capabilities, service_regions, rating, completed_orders, status,
    created_at, updated_at
)
VALUES
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
     '示範技師-林師傅', '0911222333', 'test@lock-ai.com',
     '["Yale", "Chatlock", "美樂"]'::jsonb,
     '["新北市板橋區", "台北市信義區", "桃園市中壢區"]'::jsonb,
     4.7, 23, 'active', NOW() - INTERVAL '90 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
     '陳師傅', '0922334455', 'tech-chen@example.com',
     '["Yale", "Mi-La"]'::jsonb,
     '["新北市新莊區", "新北市三重區"]'::jsonb,
     4.5, 47, 'active', NOW() - INTERVAL '120 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
     '黃師傅', '0933445566', 'tech-huang@example.com',
     '["Chatlock", "Dormakaba"]'::jsonb,
     '["台北市大安區", "台北市信義區", "台北市中山區"]'::jsonb,
     4.9, 89, 'active', NOW() - INTERVAL '60 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
     '吳師傅', '0944556677', 'tech-wu@example.com',
     '["美樂", "Yale"]'::jsonb,
     '["桃園市桃園區", "桃園市中壢區"]'::jsonb,
     4.2, 12, 'active', NOW() - INTERVAL '30 days', NOW()),
    ('77777777-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid,
     '00000000-0000-0000-0000-000000000001'::uuid,
     '66666666-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid,
     '張師傅', '0955667788', 'tech-zhang@example.com',
     '["Chatlock", "Yale", "美樂", "Dormakaba"]'::jsonb,
     '["新北市板橋區", "新北市中和區", "新北市永和區"]'::jsonb,
     4.6, 65, 'active', NOW() - INTERVAL '180 days', NOW())
ON CONFLICT (id) DO NOTHING;

-- 3) 技能矩陣＋品牌授權（僅 seed 技師 5 名——與品牌庫 zz_technician_skills.sql
--    對平；刻意不用「全 active 技師」以免動到真實註冊技師的 runtime 資料）
INSERT INTO technician_skill (technician_id, skill_code, level_id)
SELECT t.id, s.code, 'LV-B'
FROM technicians t
CROSS JOIN (VALUES ('general_locksmith'), ('electronic_lock')) AS s(code)
WHERE t.id IN (
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid
) AND t.status = 'active'
ON CONFLICT (technician_id, skill_code) DO NOTHING;

INSERT INTO technician_brand_authorization (technician_id, brand, authorized)
SELECT t.id, b.brand, TRUE
FROM technicians t
CROSS JOIN (VALUES ('Generic'), ('Yale'), ('Philips'), ('Samsung'), ('Kaadas')) AS b(brand)
WHERE t.id IN (
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa01'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa02'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa03'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa04'::uuid,
    '77777777-aaaa-4aaa-aaaa-aaaaaaaaaa05'::uuid
) AND t.status = 'active'
ON CONFLICT (technician_id, brand) DO NOTHING;

COMMIT;

-- 驗證
SELECT t.name, t.email, t.status,
       (SELECT count(*) FROM technician_skill s WHERE s.technician_id = t.id) AS skills,
       (SELECT count(*) FROM technician_brand_authorization a WHERE a.technician_id = t.id) AS brand_auths
FROM technicians t
ORDER BY t.email;
