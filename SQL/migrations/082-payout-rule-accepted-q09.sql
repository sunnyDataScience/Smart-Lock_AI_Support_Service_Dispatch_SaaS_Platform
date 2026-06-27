-- 082-payout-rule-accepted-q09.sql
-- WHY（CR-0106 / 業主裁決 2026-06-27）：師傅分潤 Q-09 原於工作簿「13 待決策 Q&A」標「待回答」、
--   technician_payout_rule（045）69 筆全 decision_status=draft/draft_review + is_mock=TRUE。業主
--   2026-06-27 裁決「提前做佣金 + 核准 21 拆帳規則草稿費率直接上線」→ Q-09 拍板，草稿費率成為
--   正式營運費率（佣金月結引擎據此計算真錢）。
-- WHAT：把既有 payout_rule 草稿列翻為 decision_status='accepted' + is_mock=FALSE（記錄 Q-09 決議）。
--   費率數值不變（業主核准草稿值原樣），僅翻狀態旗標。idempotent（已 accepted 不重寫）。
-- 註：費率仍為業主可動態調整值（Phase II Finance Config 治理）；日後改費率走 config/管理介面，非改 code。

UPDATE technician_payout_rule
   SET decision_status = 'accepted', is_mock = FALSE
 WHERE decision_status IN ('draft', 'draft_review') OR is_mock = TRUE;
