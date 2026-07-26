-- 080-technician-level.sql
-- migrate-targets: brand,tech  (LOCK-62：技師表在品牌庫與技師庫皆存在，兩庫皆須套用)
-- WHY（CR-0104 / 師傅詳情頁假資料轉真 / 業主裁決「等級=後台手動指派」）：
--   technicians 表無 level 欄，technician_service 對所有技師硬補常數 "C"（_DEFAULT_LEVEL）→
--   個資卡「等級」全技師同值、是假的。業主裁決採「手動指派」：等級成為 per-technician 可儲存、
--   可由 admin 經編輯介面調整的真實欄位（而非 code 常數）。
-- WHAT：technicians +level VARCHAR(2)（值域 S/A/B/C，API enum TechnicianLevel 強制）。
--   DEFAULT 'C'（入門級）—— 這是業務預設假設（新技師預設入門 C，admin 可調升），已於 CR-0104 §6 標明待業主確認。
--   既有列 NULL 回填 'C'。純 ADD COLUMN + UPDATE 防呆，idempotent 可重套。

ALTER TABLE technicians ADD COLUMN IF NOT EXISTS level VARCHAR(2) DEFAULT 'C';

-- 既有列若 level 為 NULL（DEFAULT 在 ADD COLUMN 後對既有列生效，但防呆顯式回填）
UPDATE technicians SET level = 'C' WHERE level IS NULL;
