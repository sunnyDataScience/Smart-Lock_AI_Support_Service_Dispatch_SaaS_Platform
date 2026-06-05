-- ============================================================================
-- 022-ai-decision-trace.sql — FR-0050 Phase II MVP: AI Governance Trace Store
-- ============================================================================
-- 目的：每個 AI 行為（reasoning/tool call/output）可回溯到 PRD source /
--      Final rule / 業主 explicit decision；audit-grade traceability。
--
-- 對齊 ADR-0028 ai-employee-charter §A. AI 不可決策清單 +
-- new spec P0 charter；Phase I ADR-0038 ai-feedback-review-policy
-- 已落地，本 FR 補 trace store。
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.ai_decision_trace (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),

  -- AI 行為類型
  decision_type       text        NOT NULL CHECK (decision_type IN (
    'reasoning',        -- LLM 推理步驟
    'tool_call',        -- 呼工具
    'output',           -- 回客戶/系統的 output
    'guardrail_block',  -- guardrail 阻擋（ADR-0030 safety_gate）
    'human_handoff'     -- 升級人工
  )),

  -- 業務 context
  conversation_id     uuid        NULL,  -- 對應 conversations.id（client 對話）
  work_order_id       uuid        NULL,  -- 對應 work_orders.id（若涉工單）
  agent_session_id    text        NULL,  -- agent run session id

  -- Traceability：source / rule / decision 三軸
  prd_source          text        NULL,  -- e.g. 'docs/_source/02-ai-chatbot-sync.md#a-m12-prd治理'
  charter_rule        text        NULL,  -- e.g. 'ADR-0028 §A.2 不可決策金額退款'
  owner_decision_ref  text        NULL,  -- e.g. 'CR-0014 HD-3=B' 業主裁決

  -- 行為詳情
  action_summary      text        NOT NULL,        -- 1-line 描述
  input_payload       jsonb       NULL,
  output_payload      jsonb       NULL,

  -- guardrail 對齊
  guardrail_triggered text        NULL,  -- 'safety_gate' / 'pii_block' / 'cost_cap' / etc.
  guardrail_action    text        NULL,  -- 'block' / 'warn' / 'redact' / 'allow'

  -- audit
  agent_version       text        NULL,  -- 'gemini-1.5-pro-002' / 'gpt-4o'
  created_at          timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ait_tenant_created_idx
  ON saas.ai_decision_trace(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ait_conversation_idx
  ON saas.ai_decision_trace(conversation_id, created_at DESC)
  WHERE conversation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ait_work_order_idx
  ON saas.ai_decision_trace(work_order_id, created_at DESC)
  WHERE work_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ait_prd_source_idx
  ON saas.ai_decision_trace(prd_source)
  WHERE prd_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS ait_charter_rule_idx
  ON saas.ai_decision_trace(charter_rule)
  WHERE charter_rule IS NOT NULL;

CREATE INDEX IF NOT EXISTS ait_decision_type_idx
  ON saas.ai_decision_trace(decision_type, created_at DESC);

COMMENT ON TABLE saas.ai_decision_trace IS
  'FR-0050 AI Governance Trace Store：每個 AI 行為對應 PRD source / '
  'Final rule / 業主裁決可回溯；audit-grade compliance review。';
