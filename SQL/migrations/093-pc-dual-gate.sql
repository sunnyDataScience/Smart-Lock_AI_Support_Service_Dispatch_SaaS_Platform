-- ═══════════════════════════════════════════════════════════════════════════
-- 093-pc-dual-gate.sql — 問題卡雙 gate schema（WBS 1.2.3 / CR-0132）
--
-- 依 15_SDS §4.6（漸進式生命週期＋雙 gate）與 18_DB §4.3 目標欄位設計：
--   Gate ①（進料/派工）：contact_phone/brand/model/failure_mode/triage_tier
--     （＋L3 條件必填 location）→ intake_completeness
--   Gate ②（知識/精煉，RMA spine）：root_cause/root_cause_category/
--     corrective_action/verification/disposition/resolution_channel/resolved_by
--     （＋L3：firmware_version/serial）→ resolution_completeness → knowledge_ready
--   精煉服務（15_SDS §9）只汲取 knowledge_ready=true 的卡；未過②不擋 operational
--   結案，卡進「待補知識佇列」。
--
-- tenant_id：直接租戶欄（原靠 conversation→users 間接推；精煉跨租戶共享池需直欄）。
-- 死欄清理：attempts/diagnosis_status/is_novel/card_id/domain_attributes——舊 harness
--   遺留（基底 Schema 已無此欄，僅存量庫可能殘留；DROP IF EXISTS 冪等）。
--
-- 慣例：IF NOT EXISTS / DROP IF EXISTS，可重複套用。落庫：品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS tenant_id               UUID,
    ADD COLUMN IF NOT EXISTS intake_completeness     FLOAT,
    ADD COLUMN IF NOT EXISTS resolution_completeness FLOAT,
    ADD COLUMN IF NOT EXISTS triage_tier             VARCHAR(10),
    ADD COLUMN IF NOT EXISTS resolution_channel      VARCHAR(30),
    ADD COLUMN IF NOT EXISTS resolved_by             UUID,
    ADD COLUMN IF NOT EXISTS contact_phone           VARCHAR(50),
    ADD COLUMN IF NOT EXISTS failure_mode            VARCHAR(60),
    ADD COLUMN IF NOT EXISTS root_cause              TEXT,
    ADD COLUMN IF NOT EXISTS root_cause_category     VARCHAR(60),
    ADD COLUMN IF NOT EXISTS corrective_action       TEXT,
    ADD COLUMN IF NOT EXISTS verification            BOOLEAN,
    ADD COLUMN IF NOT EXISTS disposition             VARCHAR(30),
    ADD COLUMN IF NOT EXISTS firmware_version        VARCHAR(50),
    ADD COLUMN IF NOT EXISTS serial                  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS knowledge_ready         BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN problem_cards.triage_tier IS 'L1/L2/L3 三層分流（15_SDS §4.6 Gate①）';
COMMENT ON COLUMN problem_cards.resolution_channel IS 'ai_auto/line_text_cs/phone_callback/onsite（L2 細分文字客服/電話回撥）';
COMMENT ON COLUMN problem_cards.disposition IS '處置分類：replacement/repair/software_update/user_education/onsite_service/ntf';
COMMENT ON COLUMN problem_cards.verification IS '是否驗證修復（8D D6）——未驗證的解法不得入知識庫';
COMMENT ON COLUMN problem_cards.knowledge_ready IS 'Gate② 通過旗標——精煉服務（15_SDS §9）只汲取 true；未過②不擋 operational 結案';
COMMENT ON COLUMN problem_cards.tenant_id IS '直接租戶欄（CR-0132；原靠 conversation 間接推）';
COMMENT ON COLUMN problem_cards.completeness_score IS '[DEPRECATED CR-0132] 由 intake_completeness/resolution_completeness 雙欄取代；保留唯讀相容';

-- tenant_id backfill（存量卡自 conversation→users 推導）
UPDATE problem_cards pc
SET tenant_id = u.tenant_id
FROM conversations c
JOIN users u ON c.user_id = u.id
WHERE pc.conversation_id = c.id AND pc.tenant_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_pc_tenant ON problem_cards (tenant_id);
-- 待補知識佇列掃描路徑（resolved 且未 knowledge_ready）
CREATE INDEX IF NOT EXISTS idx_pc_knowledge_queue
    ON problem_cards (tenant_id, updated_at DESC)
    WHERE status = 'resolved' AND knowledge_ready = FALSE;

-- 死欄清理（18_DB §4.3；僅存量庫殘留，冪等）
ALTER TABLE problem_cards
    DROP COLUMN IF EXISTS attempts,
    DROP COLUMN IF EXISTS diagnosis_status,
    DROP COLUMN IF EXISTS is_novel,
    DROP COLUMN IF EXISTS card_id,
    DROP COLUMN IF EXISTS domain_attributes;
