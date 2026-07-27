-- migrate-targets: brand
-- ============================================================================
-- 119-commission-event-outbox.sql — 佣金事件 outbox ＋ 對帳核准原子性（CR-0189）
-- ============================================================================
--
-- WHY（三個獨立缺陷，同一段程式碼）：`reconciliation_service.approve_reconciliation`
--   的四個語句在 autocommit 連線上**各自獨立提交**，且無 FOR UPDATE：
--
--   (1) 事件遺失：publish_event 失敗只 logger.exception，事件永久消失。
--       原註解宣稱「settlement 表為保底」——但保底只在 settlement 真的寫成功時成立。
--   (2) settlement 遺失（比 (1) 更嚴重）：UPDATE reconciliations 先提交、
--       INSERT settlements 後提交。中斷 → 對帳單已 approved 但 **settlement 不存在**，
--       而重試撞 `_APPROVE_FROM={'pending'}` → **永久 409、API 再也補不回來**。
--   (3) 重複出款：無 FOR UPDATE 且 settlements.reconciliation_id **只有 FK、
--       無 unique、連索引都沒有**（本檔套用前實查確認）→ 並發 approve 會產生
--       兩筆 settlement、兩次出款、兩個事件。
--
--   前端 `web/brand-portal/src/app/accounting/page.tsx` 打的正是這條 legacy 路徑，
--   所以 (2)(3) 是**生產中的金流缺陷**，非理論風險。
--
-- 本檔提供 (1) 的 outbox 表與 (3) 的唯一約束；(2) 由 service 層交易化處理。
--
-- 全 idempotent，可重複執行。
-- ============================================================================

-- ── 1. 佣金事件 outbox ───────────────────────────────────────────────────
--   欄位比照既有 line_push_outbox（SQL/Schema_v2_extensions.sql）的狀態機慣例，
--   但**多存 event_id**：`core/event_bus.publish_event` 未帶 event_id 時會**每次
--   新生成 uuid**，若 worker 重送時另生新 id，消費端 `_already_processed` 的
--   event_id 去重就完全失效（dedup 表無限成長、重播語意破裂）。故 outbox 必須
--   持有穩定 event_id，worker 重送時原樣帶入。
CREATE TABLE IF NOT EXISTS commission_event_outbox (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id          UUID NOT NULL,                       -- 穩定冪等鍵（重送時原樣帶入）
    tenant_id         UUID NOT NULL,
    topic             VARCHAR(60) NOT NULL,                -- 'commission.accrued'
    event_key         VARCHAR(64),                         -- Kafka partition key（technician_id）
    reconciliation_id UUID NOT NULL,
    settlement_id     UUID,
    payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts          INTEGER NOT NULL DEFAULT 0,
    max_attempts      INTEGER NOT NULL DEFAULT 8,
    next_attempt_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_error        TEXT,
    sent_at           TIMESTAMP WITH TIME ZONE,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_commission_outbox_status CHECK (status IN ('pending','sent','failed','dead')),
    CONSTRAINT chk_commission_outbox_attempts CHECK (attempts >= 0)
);

-- 冪等鍵取 (tenant_id, reconciliation_id) 而非 settlement_id：
-- 併發 approve 會產生**兩個不同的 settlement_id**，用 settlement_id 擋不住；
-- 一張對帳單只該有一筆佣金事件，reconciliation 才是正確的業務鍵。
CREATE UNIQUE INDEX IF NOT EXISTS uniq_commission_outbox_recon
    ON commission_event_outbox (tenant_id, reconciliation_id);

-- worker poll 主索引（只掃待送）
CREATE INDEX IF NOT EXISTS idx_commission_outbox_pending
    ON commission_event_outbox (next_attempt_at)
    WHERE status = 'pending';

COMMENT ON TABLE commission_event_outbox IS
'CR-0189 佣金事件 outbox：與 settlement 寫入**同交易**落地 → commit 後即時 publish → 失敗留 pending 由 worker 重送。取代原本「publish 失敗只 log」的永久遺失。';
COMMENT ON COLUMN commission_event_outbox.event_id IS
'穩定 event_id：publish_event 未帶此參數時每次新生成 uuid，重送會被消費端視為新事件而 dedup 失效——故必須由 outbox 持有並原樣帶入。';

-- ── 2. 堵住重複出款：settlements 對 reconciliation 唯一 ────────────────
--   一張對帳單只該產生一筆 settlement。原本連索引都沒有，並發 approve 會雙寫。
--   ⚠️ 若既有資料已有重複，本索引會建立失敗 —— 這是**刻意的**：重複出款屬財務
--      事實，必須人工確認保留哪一筆，不可由 migration 自動刪除。
--      失敗時先跑：
--        SELECT reconciliation_id, count(*), array_agg(id)
--          FROM settlements GROUP BY 1 HAVING count(*) > 1;
CREATE UNIQUE INDEX IF NOT EXISTS uniq_settlements_reconciliation
    ON settlements (reconciliation_id);

COMMENT ON INDEX uniq_settlements_reconciliation IS
'CR-0189：一張對帳單只允許一筆 settlement——原本無此約束，並發 approve 會產生兩筆＝重複出款。';
