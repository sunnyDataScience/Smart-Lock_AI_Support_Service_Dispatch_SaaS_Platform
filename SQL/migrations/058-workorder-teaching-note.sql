-- 058-workorder-teaching-note.sql
--
-- WHY（CR-0050 / BR-M08-03 完工套件）：完工套件 spec 列 photos + materials used + payment
--   status + customer sign-off + teaching note 五件；CR-0039 已做照片≥3/簽名/序號，本 migration
--   補「教學紀錄」欄位（技師現場教客戶操作之紀錄，PDF §四數位化派工單常見）。
--
-- WHAT：work_orders 補 teaching_note TEXT（nullable，向後相容）。純 ADD COLUMN，idempotent。

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS teaching_note TEXT;
COMMENT ON COLUMN work_orders.teaching_note IS 'CR-0050 BR-M08-03 完工套件：技師現場教學/操作說明紀錄';
