-- 086: 技師登入資格資料校正（backfill，冪等）
--
-- 背景（2026-07-02 師傅端測試修復，branch fix/tech-login-status-gate）：
--   technicians.status（生命週期）與 users.is_active（登入檢查點）原本脫鉤——
--   register_technician 以 is_active=TRUE 建 user、lifecycle suspend/approve 只改
--   technicians.status → 待核准/停權技師仍可登入。程式面已修：
--     1. register 改 is_active=FALSE
--     2. lifecycle 轉移同步 users.is_active =（status == 'active'）
--   本 migration 校正「修復前已存在」的存量資料。
--
-- 冪等：重跑結果相同（純狀態對齊 UPDATE）。

BEGIN;

-- 非 active 技師 → 關閉登入
UPDATE users u
SET is_active = FALSE, updated_at = NOW()
FROM technicians t
WHERE t.user_id = u.id
  AND u.role = 'technician'
  AND t.status <> 'active'
  AND u.is_active = TRUE;

-- active 技師 → 開啟登入（防呆反向對齊；正常不該有這種列）
UPDATE users u
SET is_active = TRUE, updated_at = NOW()
FROM technicians t
WHERE t.user_id = u.id
  AND u.role = 'technician'
  AND t.status = 'active'
  AND u.is_active = FALSE;

INSERT INTO schema_migrations (version, filename, note)
VALUES ('086', '086-technician-login-gate-backfill.sql',
        '技師登入資格校正：users.is_active 對齊 technicians.status（僅 active 可登入）')
ON CONFLICT (version) DO NOTHING;

COMMIT;
