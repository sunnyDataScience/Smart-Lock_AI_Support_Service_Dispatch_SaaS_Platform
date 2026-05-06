-- ============================================================================
-- Harness Framework Migration
-- ============================================================================
-- 版本：v1.0
-- 日期：2026-04-06
-- 說明：
--   1. problem_cards 表新增 Harness 欄位 (domain_attributes JSONB, attempts, 診斷狀態)
--   2. 新增 harness_traces 表 (L7 Observability 結構化追蹤)
--   3. 新增 problem_card_attempts 表 (L5 ResolutionAttempt 追蹤)
-- ============================================================================


-- ============================================================================
-- [1] problem_cards 表 — 新增 Harness 欄位
-- ============================================================================

-- domain_attributes: 動態領域欄位 (取代固定的 brand/model/category 欄位)
-- 結構: {"device_brand": "dormakaba", "device_model": "AI-99", "door_type": "推拉式", "fault_category": "verification_failure"}
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS domain_attributes JSONB DEFAULT '{}';

-- 診斷狀態機欄位
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS card_id VARCHAR(20),              -- "pc_{uuid8}" 格式 (Harness 內部 ID)
    ADD COLUMN IF NOT EXISTS diagnosis_status VARCHAR(50),     -- intake/symptom_collected/verifying/conclusion_ready/...
    ADD COLUMN IF NOT EXISTS diagnostic_round INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS symptom_summary TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS resolution_summary TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_novel BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS sop_generated BOOLEAN DEFAULT FALSE;

-- attempts: L5 ResolutionAttempt 歷程 (JSONB array)
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS attempts JSONB DEFAULT '[]';

-- GIN 索引：domain_attributes 查詢
CREATE INDEX IF NOT EXISTS idx_pc_domain_attributes ON problem_cards USING GIN (domain_attributes);

-- 索引：card_id 查詢
CREATE INDEX IF NOT EXISTS idx_pc_card_id ON problem_cards (card_id);

-- 索引：診斷狀態
CREATE INDEX IF NOT EXISTS idx_pc_diagnosis_status ON problem_cards (diagnosis_status);

COMMENT ON COLUMN problem_cards.domain_attributes IS 'Harness L1: 動態領域欄位 (JSONB)，schema 由 config.toml [harness.task.domain_schema] 定義';
COMMENT ON COLUMN problem_cards.card_id IS 'Harness 內部 ProblemCard ID (pc_{uuid8} 格式)';
COMMENT ON COLUMN problem_cards.diagnosis_status IS 'Harness L1: 診斷狀態機當前狀態 (PDCA lifecycle)';
COMMENT ON COLUMN problem_cards.attempts IS 'Harness L5: ResolutionAttempt 歷程 (JSONB array of {timestamp, agent_name, strategy, result, quality_score})';


-- ============================================================================
-- [2] harness_traces 表 — L7 Observability 結構化追蹤
-- ============================================================================

CREATE TABLE IF NOT EXISTS harness_traces (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(100) NOT NULL,        -- LangGraph thread_id
    node_name       VARCHAR(50) NOT NULL,          -- e.g. "task_decompose", "router", "safety_gate"
    timestamp       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(10) NOT NULL,           -- "ok" | "error"
    duration_ms     FLOAT,                          -- 節點執行耗時 (毫秒)
    history_tag     VARCHAR(200),                   -- e.g. "task_decompose:round_1:verifying"
    diagnosis_status VARCHAR(50),                   -- 當前診斷狀態 (from task output)
    symptoms        JSONB,                          -- 累積的症狀 ID 列表
    error           TEXT,                           -- 錯誤訊息 (status=error 時)
    metadata        JSONB DEFAULT '{}'              -- 額外 metadata (token count, model, etc.)
);

-- 索引：按 session 查詢
CREATE INDEX IF NOT EXISTS idx_ht_session ON harness_traces (session_id);
-- 索引：按時間查詢
CREATE INDEX IF NOT EXISTS idx_ht_timestamp ON harness_traces (timestamp DESC);
-- 索引：按節點名查詢
CREATE INDEX IF NOT EXISTS idx_ht_node ON harness_traces (node_name);

COMMENT ON TABLE harness_traces IS 'Harness L7: 結構化追蹤事件，每個 graph 節點執行都產生一筆';
COMMENT ON COLUMN harness_traces.session_id IS 'LangGraph thread_id，對應一個完整對話 session';
COMMENT ON COLUMN harness_traces.duration_ms IS '節點執行耗時 (毫秒)，用於 latency 監控';


-- ============================================================================
-- [3] user_facts 表 — SCD Type 2 用戶屬性歷史紀錄
-- ============================================================================
-- 用途：儲存 device_brand / device_model / phone / address 等用戶硬事實
-- 寫入時 expire 舊版本（is_current=FALSE + end_date=NOW），插入新版本
-- 讀取一律 WHERE is_current=TRUE
-- 此前 schema 由 agent/profiles/manager.py 動態建立（runtime CREATE TABLE IF NOT EXISTS），
-- 自 RP1.C.4 起改由本 SQL 檔統一管理；新環境部署前必須先跑此檔。
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_facts (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    attr_key VARCHAR(100) NOT NULL,
    attr_val TEXT NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    start_date TIMESTAMP DEFAULT NOW(),
    end_date TIMESTAMP
);

COMMENT ON TABLE user_facts IS 'SCD Type 2 用戶硬事實：device_brand / device_model / phone / address 等';
COMMENT ON COLUMN user_facts.is_current IS 'TRUE = 最新版本；FALSE = 已被新值取代（保留歷史）';
COMMENT ON COLUMN user_facts.start_date IS '此版本生效時間';
COMMENT ON COLUMN user_facts.end_date IS '此版本失效時間（is_current=FALSE 時非 NULL）';
