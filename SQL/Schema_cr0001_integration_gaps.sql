-- CR-0001 / ADR-0029 / ADR-0030 integration gap repair migrations
-- Created: 2026-05-16
--
-- Bundles 3 schema changes from CR-0001:
--   1. conversations.last_problem_card_id (Phase C1 — bidirectional FK)
--   2. webhook_idempotency table         (Phase C2 — webhook retry guard)
--   3. tenant_id columns                 (Phase C3 — ADR-0030 propagation)
--
-- All changes are additive + nullable / default-bearing → safe online migration,
-- backward compatible with running agent/api processes.

BEGIN;

-- ─────────────────────────────────────────────
-- 1. Phase C1 — conversations ↔ problem_cards 雙向 FK
-- ─────────────────────────────────────────────

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS last_problem_card_id UUID NULL
        REFERENCES problem_cards(id) ON DELETE SET NULL;

COMMENT ON COLUMN conversations.last_problem_card_id IS
'CR-0001 §5 / Phase C1：對話最近一次自動建立的 ProblemCard。'
'admin dashboard 用此快速從 conversation 跳到 PC；NULL = 此對話從未產生 PC。';

CREATE INDEX IF NOT EXISTS idx_conversations_last_problem_card_id
    ON conversations (last_problem_card_id)
    WHERE last_problem_card_id IS NOT NULL;


-- ─────────────────────────────────────────────
-- 2. Phase C2 — LINE webhook idempotency table
-- ─────────────────────────────────────────────
--
-- CR-0001 §8 Q5 (a)：TTL 7 天（LINE 最長重送 24h，buffer 充裕）。
-- partial index 只 cover 未過期 row，控制 index size。

CREATE TABLE IF NOT EXISTS webhook_idempotency (
    event_id      TEXT PRIMARY KEY,
                                    -- LINE event.message.id 或 event.webhookEventId
    processed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    source        VARCHAR(32) NOT NULL DEFAULT 'line',
                                    -- 'line' / 'web_test' / 等未來 webhook 源
    tenant_id     VARCHAR(50) NOT NULL DEFAULT 'default'
);

CREATE INDEX IF NOT EXISTS idx_webhook_idempotency_processed_at
    ON webhook_idempotency (processed_at)
    WHERE processed_at > NOW() - INTERVAL '7 days';

COMMENT ON TABLE webhook_idempotency IS
'CR-0001 §8 Q5 / Phase C2：LINE webhook 重送防護。'
'入口先 SELECT event_id；命中 → 直接 200 不再進業務邏輯。'
'7 天 TTL；cleanup job 定期 DELETE WHERE processed_at < NOW() - 7d。';


-- ─────────────────────────────────────────────
-- 3. Phase C3 — tenant_id propagation (ADR-0030)
-- ─────────────────────────────────────────────
--
-- 加 tenant_id 到所有 agent-side 寫入的表，預設 'default'。
-- 既有資料 backfill 'default'；single-tenant 部署無感升級。

DO $$
BEGIN
    -- audit_log: schema 由 Schema_v2_extensions.sql 建
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_log') THEN
        ALTER TABLE audit_log
            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
    END IF;

    -- user_facts: schema 由 Schema_harness_migration.sql 建
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_facts') THEN
        ALTER TABLE user_facts
            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_user_facts_tenant_user
            ON user_facts (tenant_id, user_id);
    END IF;

    -- agent_outbox: Phase B2 worker 也會撈 tenant_id 決定 X-Tenant-ID header
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_outbox') THEN
        ALTER TABLE agent_outbox
            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
    END IF;

    -- belief_states: Turn Cycle 持久化
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'belief_states') THEN
        ALTER TABLE belief_states
            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
    END IF;

    -- data_corrections: review queue (Phase B3)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'data_corrections') THEN
        ALTER TABLE data_corrections
            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
    END IF;

    -- llm_usage_log: cost / token tracking
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'llm_usage_log') THEN
        ALTER TABLE llm_usage_log
            ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50) NOT NULL DEFAULT 'default';
    END IF;
END$$;

COMMIT;
