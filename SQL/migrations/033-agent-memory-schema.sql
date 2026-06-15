-- 033-agent-memory-schema.sql
-- CR-0023 / ADR-0113：agent per-user 記憶後端 SQLite → Postgres。
-- LockCore CS agent 的 per-user 記憶與轉真人稽核紀錄，從本地 SQLite(FTS5 trigram)
-- 遷到 lock-ai Cloud SQL 的獨立 schema `agent`，與營運 saas.* / public.* 隔離。
--
-- 設計(見 ADR-0113 / CR-0023 §8)：
--   - 獨立 schema `agent`：乾淨隔離，不污染 saas/public，連線沿用同一 POSTGRES_URI。
--   - tenant 仍存字串(如 'locksmart')：agent 端不對齊 saas 的 UUID tenant_id(§8 決策)。
--   - 中文子字串檢索:SQLite FTS5 trigram → Postgres pg_trgm + GIN(ILIKE 加速 + similarity 排序)。
--   - created_at / updated_at 用 BIGINT epoch 秒，對齊 MemoryEntry/EscalationRecord dataclass(int)。
--   - 核心不變量:所有讀寫帶 tenant+user_id(default deny)在應用層 store 強制，DB 以索引支撐。

-- ── 0. 前置:schema 與 pg_trgm extension ──────────────────────────────────
CREATE SCHEMA IF NOT EXISTS agent;

-- pg_trgm 為 Cloud SQL 內建 extension；提供 trigram 相似度 + GIN 加速 ILIKE 子字串檢索。
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── 1. agent.memory_entry：per-user 記憶 ──────────────────────────────────
CREATE TABLE IF NOT EXISTS agent.memory_entry (
    id             BIGSERIAL PRIMARY KEY,
    tenant         TEXT   NOT NULL,
    user_id        TEXT   NOT NULL,
    kind           TEXT   NOT NULL,   -- profile / preference / fact / issue / dispatch(應用層 VALID_KINDS 驗證)
    content        TEXT   NOT NULL,
    source_session TEXT,
    created_at     BIGINT NOT NULL,   -- epoch 秒
    updated_at     BIGINT NOT NULL
);

COMMENT ON TABLE agent.memory_entry IS
    'CR-0023/ADR-0113 LockCore CS agent per-user 記憶(對齊舊 SQLite memory_entry)';

-- scope 查詢索引(tenant+user_id+kind)— 對齊 SQLite idx_mem_scope。
CREATE INDEX IF NOT EXISTS idx_agent_mem_scope
    ON agent.memory_entry (tenant, user_id, kind);

-- 近期排序(list_for_user ORDER BY updated_at DESC)。
CREATE INDEX IF NOT EXISTS idx_agent_mem_recent
    ON agent.memory_entry (tenant, user_id, updated_at DESC);

-- 中文子字串全文檢索:trigram GIN 加速 content ILIKE '%q%'(取代 FTS5)。
CREATE INDEX IF NOT EXISTS idx_agent_mem_content_trgm
    ON agent.memory_entry USING gin (content gin_trgm_ops);

-- ── 2. agent.escalation：轉真人 / 派工稽核紀錄 ────────────────────────────
CREATE TABLE IF NOT EXISTS agent.escalation (
    id             BIGSERIAL PRIMARY KEY,
    tenant         TEXT    NOT NULL,
    user_id        TEXT    NOT NULL,
    reason         TEXT    NOT NULL,
    is_explicit    BOOLEAN NOT NULL DEFAULT FALSE,
    facts_snapshot JSONB   NOT NULL DEFAULT '{}'::jsonb,
    created_at     BIGINT  NOT NULL   -- epoch 秒
);

COMMENT ON TABLE agent.escalation IS
    'CR-0023/ADR-0113 LockCore CS agent 轉真人稽核紀錄(對齊舊 SQLite escalation)';

CREATE INDEX IF NOT EXISTS idx_agent_escalation_user
    ON agent.escalation (tenant, user_id, created_at DESC);
