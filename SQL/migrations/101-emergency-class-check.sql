-- 101-emergency-class-check.sql
--
-- WHY（CR-0165 F2 / UAT wave1）：
--   problem_cards.emergency_class 由 091 引入僅 VARCHAR(30) 無約束；急件 carve-out
--   消費端（work_order_service / quote_engine_service）全部只判 IS NOT NULL——任意
--   字串一旦繞過 API 直接入庫（psql/seed/未來新寫入點）即被當急件跳過報價 gate。
--   應用層 _VALID_EMERGENCY_CLASSES 已驗四類，本 migration 補 DB 層 defense-in-depth。
--
-- WHAT：CHECK（NULL 允許＝非急件；四類=locked_out/trapped_inside/safety_risk/
--   angry_high_risk）。NOT VALID 先掛約束不掃全表，VALIDATE 分離執行——存量違規時
--   明確報錯定位而非 ADD CONSTRAINT 整句失敗。idempotent 可重套。
--
-- 套用前預檢（唯讀）：
--   SELECT id, emergency_class FROM problem_cards
--   WHERE emergency_class IS NOT NULL
--     AND emergency_class NOT IN ('locked_out','trapped_inside','safety_risk','angry_high_risk');
--   （查出違規列的處置——remap 四類或清 NULL——依 CR-0165 §8-4 留待 prod 套用時裁決）

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_problem_cards_emergency_class'
          AND conrelid = 'problem_cards'::regclass
    ) THEN
        ALTER TABLE problem_cards
            ADD CONSTRAINT chk_problem_cards_emergency_class
            CHECK (
                emergency_class IS NULL
                OR emergency_class IN (
                    'locked_out', 'trapped_inside', 'safety_risk', 'angry_high_risk'
                )
            ) NOT VALID;
    END IF;
END $$;

ALTER TABLE problem_cards VALIDATE CONSTRAINT chk_problem_cards_emergency_class;
