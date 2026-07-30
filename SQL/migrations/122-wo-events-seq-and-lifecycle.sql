-- ============================================================================
-- 122-wo-events-seq-and-lifecycle.sql  —— CR-0193
-- ============================================================================
-- WHY：
--   正典 20_Test_Cases.md:258（TC-WO-01）要求「寫入 work_order_events（事件溯源 seq）」。
--   UAT 2026-07-29 實測 FAIL（UAT-D-007）：
--     1. 無 seq 欄——只有 created_at，一筆被刪的事件在事後查核不留痕跡，
--        「溯源」不成立。
--     2. 10 個生命週期轉換只有 reject / assign / reassign 三個寫事件；
--        建單 / 接單 / 完工 / 取消 / 重開 / 升級 / 確認七個都沒有。
--        （subflow 事件反而齊全，因為它們走共用 recorder _append_subflow_event，
--         生命週期轉換則各自手寫 INSERT，漏了沒有機制會發現。）
--
-- WHAT：
--   1. seq INTEGER —— per-工單連號（1,2,3…）。選 per-工單而非全域 BIGSERIAL 的
--      理由：全域序列的缺號無法區分「別的工單佔號」與「事件被刪」，等於沒有
--      溯源價值。連號才能靠缺號發現遺失。
--   2. backfill 既有列（依 created_at, id 排序）後才 SET NOT NULL——
--      NOT NULL 是刻意的：留 NULL 的事件會在連號上開洞，讓缺號偵測失效。
--   3. UNIQUE (work_order_id, seq) —— 連號的強制點，同時是併發取號的正確性靠山
--      （service 層用單語句 COALESCE(MAX(seq),0)+1 取號，撞號由此擋下 → 重試）。
--   4. event_type CHECK 補 7 個生命週期值。
--   5. 索引 (work_order_id, seq DESC) 供 API 依 seq 排序。
--
-- ⚠️ 部署順序：本 migration **必須先於 code 套用**。code 端 _insert_wo_event 與
--    list_work_order_events 都引用 seq 欄，欄位不存在時事件讀寫全數 500。
--
-- ⚠️ idempotency：CHECK 一律 DROP IF EXISTS 再 ADD（不可用「比對約束定義內容」
--    當守衛——016 的教訓：帶內容比對的守衛套用一次後就再也匹配不到，
--    第二次 run 會炸 already exists）。
-- ============================================================================

-- ── 1. seq 欄（先 nullable 才能 backfill）────────────────────────────────────
ALTER TABLE work_order_events ADD COLUMN IF NOT EXISTS seq INTEGER;

-- ── 2. backfill 既有列 ──────────────────────────────────────────────────────
-- WHERE seq IS NULL 保證可重套：第二次 run 時全部已有值 → 命中 0 列。
-- 單一 UPDATE 語句具原子性，不會留下「一半有號一半沒號」的中間態。
WITH numbered AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY work_order_id ORDER BY created_at, id
           ) AS rn
    FROM work_order_events
    WHERE seq IS NULL
)
UPDATE work_order_events e
SET seq = n.rn
FROM numbered n
WHERE e.id = n.id AND e.seq IS NULL;

-- ── 3. NOT NULL（backfill 後）─────────────────────────────────────────────
-- 已是 NOT NULL 時本句為 no-op；若 backfill 有漏則會 fail loud（正確行為）。
ALTER TABLE work_order_events ALTER COLUMN seq SET NOT NULL;

-- ── 4. UNIQUE (work_order_id, seq) ─────────────────────────────────────────
-- 用 conname 存在性當守衛（002/003/010 的既有做法，可重套）。
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'work_order_events_wo_seq_key'
    ) THEN
        ALTER TABLE work_order_events
            ADD CONSTRAINT work_order_events_wo_seq_key UNIQUE (work_order_id, seq);
    END IF;
END $$;

-- ── 5. event_type CHECK 補生命週期值 ───────────────────────────────────────
-- 同 050 / 059 / 102 / 104 的做法（本檔是第 5 次為加值改同一條 CHECK；
-- 後續建議另開 CR 改為參照表以終結這串 migration）。
ALTER TABLE work_order_events DROP CONSTRAINT IF EXISTS work_order_events_event_type_check;
ALTER TABLE work_order_events ADD CONSTRAINT work_order_events_event_type_check
    CHECK (event_type IN (
        'scope_change',
        'material_request',
        'delay',
        'door_check',
        'signature_submitted',
        'reschedule_proposed',
        'schedule_conflict',   -- migration 050
        'arrival',             -- migration 059 (CR-0053)
        'reassign',            -- migration 059 (CR-0053)
        'assign',              -- migration 102 (CR-0165)
        'supply_arrived',      -- migration 102 (CR-0165)
        'reject',              -- migration 104 (CR-0166 R1)
        'created',             -- migration 122 (CR-0193) 問題卡→工單轉換
        'accepted',            -- migration 122 (CR-0193) 技師接單
        'completed',           -- migration 122 (CR-0193) 完工
        'cancelled',           -- migration 122 (CR-0193) 取消
        'reopened',            -- migration 122 (CR-0193) 重開
        'escalated',           -- migration 122 (CR-0193) 升級
        'confirmed',           -- migration 122 (CR-0193) 客服確認
        'other'
    ));

-- ── 6. 索引 ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_wo_events_wo_seq
    ON work_order_events (work_order_id, seq DESC);

COMMENT ON COLUMN work_order_events.seq IS
    'CR-0193 per-工單事件連號（1 起遞增）。溯源用：缺號即代表事件遺失。'
    '所有寫入必須經 work_order_service._insert_wo_event 取號。';
