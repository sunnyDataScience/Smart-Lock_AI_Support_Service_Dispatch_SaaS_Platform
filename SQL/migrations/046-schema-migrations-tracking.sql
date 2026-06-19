-- 046-schema-migrations-tracking.sql
-- CR-0038 階段0：建立 migration 套用追蹤表，根治「registry 標記 ≠ 各環境實際套用」雙向漂移。
--
-- 背景（2026-06-19 對抗式盤點 CR-0038 發現）：
--   MIGRATION_REGISTRY.md 把 035/045 標 🟢 idempotent，但 dev DB 實際無此兩表
--   （test_password_reset / test_cr_0037 直接 UndefinedTable FAIL）；
--   反之 017-027 標 🟡 pending 卻早已套用。registry 是人工維護的「意圖」，非「事實」。
--   本表讓 apply 腳本（scripts/db/apply-schema-prod.sh）每套一支即留痕，
--   `SELECT version FROM schema_migrations` 才是各環境的真實狀態。
--
-- 全 IF NOT EXISTS 可重套。

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version     TEXT PRIMARY KEY,              -- migration 編號前綴，如 '045'
    filename    TEXT NOT NULL,                 -- 完整檔名，如 '045-technician-payout-rule.sql'
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    note        TEXT                           -- 'baseline'（建表前回填）/ 'applied' / 人工備註
);

COMMENT ON TABLE public.schema_migrations IS
    'CR-0038 階段0：migration 套用真實狀態（取代 MIGRATION_REGISTRY.md 的人工意圖標記）';
