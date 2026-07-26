-- 116-audit-chain-checkpoint.sql
-- CR-0184（UAT-0723-F3）：audit hash-chain re-baseline checkpoint。
--
-- 落庫：品牌庫（audit_events 所在，部署層級全域鏈，無 tenant_id）。
--
-- 背景：verify_audit_chain 回 valid:false，根因＝CR-0166 R1-5 advisory lock 部署前
--   （~2026-07-12）的並發競態造成 5 個歷史鏈分叉（兩三筆同時讀同一 prev_hash 各自
--   append）。lock 上線後零分叉、寫入路徑已正確。歷史分叉無法「解叉」（改 entry_hash
--   即破壞既有防竄改證據），故採業主裁決之非破壞式 re-baseline：記錄一個 known-good
--   基準雜湊，verify 從基準列之後起驗（歷史保留不刪，僅標記為凍結基準）。
--
-- 純 CREATE TABLE IF NOT EXISTS，可重套。
CREATE TABLE IF NOT EXISTS audit_chain_checkpoint (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 基準列的 entry_hash：verify 從此雜湊「之後」的列起算（該列本身視為已凍結歷史）
    baseline_entry_hash  TEXT NOT NULL,
    -- 基準列定位（(created_at,id) 為鏈序 index 鍵；用於精準界定「基準之後」）
    baseline_row_id      uuid,
    baseline_created_at   timestamptz,
    note                 TEXT,
    created_by           uuid,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_chain_checkpoint_created_at
    ON audit_chain_checkpoint (created_at DESC);

COMMENT ON TABLE audit_chain_checkpoint IS
    'CR-0184：audit hash-chain re-baseline 基準點；verify 從最新 checkpoint 的 baseline_entry_hash 之後起驗（歷史凍結不刪）';
