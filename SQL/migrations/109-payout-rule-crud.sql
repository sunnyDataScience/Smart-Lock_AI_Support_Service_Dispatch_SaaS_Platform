-- 109-payout-rule-crud.sql
--
-- WHY（UAT-0718 W1-6 / 業主裁決「拆帳規則完整 CRUD」）：
--   technician_payout_rule（045）純唯讀主檔——無編輯能力、生效日恆「—」。
--   業主裁決補完整 CRUD（新增/編輯/停用），比照 quote_catalog（CR-0110）軟刪模式，
--   每次寫入硬性記 audit_events（拆帳牽師傅佣金，稽核不可缺漏）。
--
-- WHAT：technician_payout_rule 加 updated_at / deleted_at 兩欄（nullable/預設現值），
--   支援軟刪（deleted_at IS NULL = 生效列）與編輯留痕。CRUD 端點見 catalog_v2.py。
--
-- 性質：forward-only、idempotent（ADD COLUMN IF NOT EXISTS 可重套）。

ALTER TABLE technician_payout_rule
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE technician_payout_rule
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN technician_payout_rule.updated_at IS '最後編輯時間（CRUD 留痕）；UAT-0718 W1-6';
COMMENT ON COLUMN technician_payout_rule.deleted_at IS '軟刪/停用時間（NULL=生效列，比照 quote_catalog CR-0110）；UAT-0718 W1-6';
