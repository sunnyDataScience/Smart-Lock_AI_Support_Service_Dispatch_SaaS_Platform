-- ============================================================================
-- Harness Framework Migration
-- ============================================================================
-- 版本：v1.1
-- 日期：2026-04-06（2026-07-08 清理：harness 架構已於 2026-06-04 隨 LockCore
--       重寫刪除，本檔移除兩張零引用死表 harness_traces / user_soft_profiles
--       的 CREATE 區塊——既有環境的存量表不受影響，只是新環境不再建。
--       歷史 DDL 查 git。）
-- 說明：
--   1. problem_cards 表新增 Harness 欄位 (domain_attributes JSONB, attempts, 診斷狀態)
--      —— problem_card_service.py 仍在使用，保留
--   2. user_facts 表 (SCD Type 2 用戶硬事實) —— data_corrections/facts_erp_sync 在用，保留
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
-- [2] user_facts 表 — SCD Type 2 用戶屬性歷史紀錄
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
