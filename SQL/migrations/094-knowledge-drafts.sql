-- ═══════════════════════════════════════════════════════════════════════════
-- 094-knowledge-drafts.sql — knowledge-refinery Draft Queue(WBS 2.3.1 / CR-0139)
--
-- ADR-018 精煉五步的步驟②③銜接層:提煉分流器產出的 draft 落此表,
-- 供 2.3.2 HITL 審核 UI 消費(diff / 核可 / 拒絕 / 退回重煉)。
-- 狀態機(15_SDS §9.2):pending_review → approved / rejected / re_refine;
-- re_refine 重煉時舊 draft 標 superseded(append-only 精神,不刪列)。
--
-- 冪等:draft_key = sha256(card_id + draft_type + 正規化內容)[:16],
-- UNIQUE(tenant_id, draft_key) → 重跑汲取不產生重複 draft。
-- 落庫:品牌庫(與 problem_cards / conversations 同庫,可 FK 溯源)。
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS knowledge_drafts (
    id                      BIGSERIAL PRIMARY KEY,
    tenant_id               UUID NOT NULL,
    draft_key               VARCHAR(32) NOT NULL,
    -- 兩軌分流(ADR-018 步驟②):case_entry=事實軌(案例史)、behavior=行為軌(skill SOP 候選)
    draft_type              VARCHAR(20) NOT NULL CHECK (draft_type IN ('case_entry', 'behavior')),
    source_problem_card_id  UUID REFERENCES problem_cards(id) ON DELETE SET NULL,
    source_conversation_id  UUID REFERENCES conversations(id) ON DELETE SET NULL,
    brand                   VARCHAR(100),
    model                   VARCHAR(100),
    category                VARCHAR(50),
    title                   VARCHAR(255) NOT NULL,
    -- 結構化草稿:case_entry={symptom, resolution};behavior={proposal, target_skill, rationale}
    payload                 JSONB NOT NULL,
    -- 溯源(HITL 硬 gate 的審計基礎):{problem_card_id, conversation_id, message_count,
    --   spine 快照(root_cause/corrective_action/...), llm_model, refined_at}
    provenance              JSONB NOT NULL,
    confidence              REAL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'approved', 'rejected', 're_refine', 'superseded')),
    review_comment          TEXT,
    reviewed_by             UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, draft_key)
);

-- 審核佇列主查詢:tenant + 狀態 + 時間序
CREATE INDEX IF NOT EXISTS idx_knowledge_drafts_queue
    ON knowledge_drafts (tenant_id, status, created_at DESC);

-- 汲取層反查:某卡是否已有 draft(冪等 intake 的 NOT EXISTS 子查詢)
CREATE INDEX IF NOT EXISTS idx_knowledge_drafts_card
    ON knowledge_drafts (source_problem_card_id);
