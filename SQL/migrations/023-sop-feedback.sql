-- ============================================================================
-- 023-sop-feedback.sql — FR-0051 Phase II MVP: SOP Feedback Spiral
-- ============================================================================
-- 目的：SOP 持續優化迴圈 — 多源 feedback aggregate → review queue → impact 追蹤。
--
-- 對齊 FR-0051 §1：feedback 多源 (customer thumbs up/down / 技師 onsite report /
--                  RMA findings / AI Eval / CSM manual flag) → aggregate
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.sop_feedback (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),

  -- 對應的 SOP（sop_drafts.id 或 case_entries.id — published 後）
  sop_id              uuid        NOT NULL,
  sop_type            text        NOT NULL CHECK (sop_type IN ('draft', 'case_entry')),

  -- feedback 來源（多源 aggregate）
  source              text        NOT NULL CHECK (source IN (
    'customer_thumbs',     -- 客戶 thumbs up/down 評價
    'technician_onsite',   -- 技師現場執行回報
    'rma_finding',         -- RMA 品質回饋
    'ai_eval',             -- AI Eval (FR-0032)
    'csm_manual'           -- CSM 手動標記
  )),

  -- 評分維度
  sentiment           text        NOT NULL CHECK (sentiment IN (
    'positive', 'neutral', 'negative'
  )),
  score               numeric(3,1) NULL CHECK (
    score IS NULL OR (score >= 1.0 AND score <= 5.0)
  ),

  -- feedback 詳情
  comment             text        NULL,
  metadata            jsonb       NULL,    -- 額外 context (e.g. wo_id, rma_id, ai_eval_id)

  -- 來源 user / 工單參照
  reporter_user_id    uuid        NULL,
  work_order_id       uuid        NULL,

  created_at          timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sop_fb_tenant_sop_idx
  ON saas.sop_feedback(tenant_id, sop_id, created_at DESC);

CREATE INDEX IF NOT EXISTS sop_fb_source_idx
  ON saas.sop_feedback(source, created_at DESC);

CREATE INDEX IF NOT EXISTS sop_fb_sentiment_idx
  ON saas.sop_feedback(sop_id, sentiment);

COMMENT ON TABLE saas.sop_feedback IS
  'FR-0051 SOP Feedback Spiral 多源 feedback aggregate 表。'
  '5 來源：customer_thumbs / technician_onsite / rma_finding / ai_eval / csm_manual';
