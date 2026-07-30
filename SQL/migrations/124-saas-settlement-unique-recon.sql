-- ============================================================================
-- 124-saas-settlement-unique-recon.sql  —— CR-0189 §8 選項 a（業主 2026-07-30 裁決）
-- ============================================================================
-- WHY：
--   業主裁決「v2 co_sign_reconciliation 也要走 outbox 發 commission.accrued」，
--   以解開 SC-09／SC-13 的驗收阻塞。但實作時發現 v2 的問題比「缺事件」更嚴重：
--
--   CR-0189 在 legacy `approve_reconciliation` 修掉的兩個缺陷，**v2 一個都沒修**：
--     ① 非原子：v2 的 `UPDATE reconciliation` 與 `INSERT saas.settlement` 在
--        autocommit 下是兩個交易，中間死掉就留下 approved 但無 settlement（漏出款）。
--     ② 無列鎖 + 無唯一約束：兩個並發 co-sign 都讀到 in_review → 各建一筆
--        settlement → **重複出款**。
--        legacy 有 `uniq_settlements_reconciliation`，`saas.settlement`
--        **只有非唯一** 索引 `settlement_tenant_recon_idx`。
--
--   而 outbox 模式的全部意義就是「事件與 settlement 同生共死」——掛在一條非交易
--   路徑上等於沒有保證。所以修原子性不是額外範圍，是加事件的**前置條件**。
--
-- WHAT：`saas.settlement` 加 `UNIQUE (reconciliation_id)`，與 legacy 對齊。
--   月結批次建立的 settlement 其 `reconciliation_id` 為 NULL；Postgres 的唯一索引
--   允許多個 NULL，故不影響月結路徑。
--
-- ⚠️ 套用前先查存量重複（**有列必須人工裁定，不可自動刪**——出款紀錄）：
--     SELECT reconciliation_id, count(*), array_agg(id)
--       FROM saas.settlement WHERE reconciliation_id IS NOT NULL
--      GROUP BY 1 HAVING count(*) > 1;
--   本機 2026-07-30 查證：saas.settlement 0 筆、重複 0 組、approved 無 settlement 0 筆。
--   prod 未查（需 gcloud auth）——**有重複時本 migration 會 fail loud，這是正確行為**，
--   不要為了讓它過而先刪列。
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uniq_saas_settlement_reconciliation'
    ) THEN
        ALTER TABLE saas.settlement
            ADD CONSTRAINT uniq_saas_settlement_reconciliation UNIQUE (reconciliation_id);
    END IF;
END $$;

COMMENT ON CONSTRAINT uniq_saas_settlement_reconciliation ON saas.settlement IS
    'CR-0189 §8a：一張對帳單只能有一筆 settlement（防並發 co-sign 重複出款）。'
    '月結批次的 settlement reconciliation_id 為 NULL，不受此約束（多 NULL 合法）。';
