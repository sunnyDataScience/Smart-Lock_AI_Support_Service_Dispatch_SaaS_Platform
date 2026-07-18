-- 108-intake-case-links.sql
--
-- WHY（UAT-0718 W5-4 / 第二輪代理 UAT P2-13）：
--   進線案件是資訊孤島——saas.intake_case 無 conversation / problem_card /
--   work_order 關聯欄位，LINE 自動建案看不到來源對話與後續單。085 只做了
--   下游反向鏈（problem_cards/work_orders.case_id），案件本體無正向鏈。
--
-- WHAT（已釘契約）：saas.intake_case 加三個 nullable uuid 關聯欄
--   conversation_id / problem_card_id / work_order_id（弱關聯不下 FK——
--   對話與卡/單可能被清理，案件為稽核容器需獨立存活）。
--   LINE 自動建案路徑（problem_card_service._ensure_line_case）回填
--   conversation_id + problem_card_id；手動建案 UI 端可不填（NULL）。
--   ADD COLUMN IF NOT EXISTS 可重套（idempotent）。

ALTER TABLE saas.intake_case
    ADD COLUMN IF NOT EXISTS conversation_id UUID;
ALTER TABLE saas.intake_case
    ADD COLUMN IF NOT EXISTS problem_card_id UUID;
ALTER TABLE saas.intake_case
    ADD COLUMN IF NOT EXISTS work_order_id UUID;

COMMENT ON COLUMN saas.intake_case.conversation_id IS '來源對話（LINE 自動建案回填；弱關聯無 FK）；UAT-0718 W5-4';
COMMENT ON COLUMN saas.intake_case.problem_card_id IS '關聯問題卡（弱關聯無 FK）；UAT-0718 W5-4';
COMMENT ON COLUMN saas.intake_case.work_order_id IS '關聯工單（弱關聯無 FK）；UAT-0718 W5-4';

-- 反查索引（前端「有值才渲染連結」的常用查詢面）
CREATE INDEX IF NOT EXISTS idx_intake_case_conversation
    ON saas.intake_case(conversation_id) WHERE conversation_id IS NOT NULL;
