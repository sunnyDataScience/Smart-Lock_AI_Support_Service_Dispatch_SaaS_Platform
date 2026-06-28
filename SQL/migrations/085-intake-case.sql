-- 085-intake-case.sql
-- WHY（CR-0108 / 業主裁決 2026-06-28）：M01 進線入口完成度 12%（Phase I 最低），業主核心
--   目標「接單從客服一路串到工單」最前端斷點 —— 現況無跨渠道可追蹤的「Case/Inquiry」實體，
--   電話/Web/熟客介紹進線無客服代建入口、無報價前建 Case、無 first-response SLA 計時。
-- WHAT：新表 saas.intake_case（Case=一次進線事件，上游容器，下可含多 problem_card/work_order）。
--   D1 渠道 = line/phone/web/referral（partner 4 渠道留 Phase II）；D3 漸進 = problem_cards/
--   work_orders 加 nullable case_id 先建關聯不硬擋；D5 可讀號 C-NNNNNN（per-tenant 序列）。
--   idempotent（CREATE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS）。

CREATE TABLE IF NOT EXISTS saas.intake_case (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id             UUID NOT NULL,
    case_number           VARCHAR(20) NOT NULL,                 -- D5 可讀號 C-NNNNNN
    source_channel        VARCHAR(20) NOT NULL DEFAULT 'line'
                          CHECK (source_channel IN ('line', 'phone', 'web', 'referral')),  -- D1
    customer_id           UUID,                                 -- 既有 users(line_user) 比對到則填
    customer_name         VARCHAR(120),
    customer_phone        VARCHAR(20),
    customer_line_id      VARCHAR(64),
    summary               TEXT,                                 -- 需求摘要
    status                VARCHAR(20) NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open', 'in_progress', 'closed')),
    first_response_due_at TIMESTAMP WITH TIME ZONE,             -- 建案 + SLA 級距 computed
    first_responded_at    TIMESTAMP WITH TIME ZONE,            -- 首次回應時間（NULL=未回應）
    created_by            UUID,                                 -- 建案客服 actor
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- D5 可讀號序列（全租戶共用流水；號碼不敏感、不需 per-tenant 隔離）
CREATE SEQUENCE IF NOT EXISTS saas.intake_case_number_seq;

CREATE INDEX IF NOT EXISTS idx_intake_case_tenant ON saas.intake_case(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_case_channel ON saas.intake_case(tenant_id, source_channel);
CREATE INDEX IF NOT EXISTS idx_intake_case_status ON saas.intake_case(tenant_id, status);
-- SLA 逾時掃描：未回應且已到期
CREATE INDEX IF NOT EXISTS idx_intake_case_sla_due ON saas.intake_case(first_response_due_at)
    WHERE first_responded_at IS NULL;

-- D3 漸進：problem_cards / work_orders 加 nullable case_id（先建關聯，不硬擋）
ALTER TABLE problem_cards ADD COLUMN IF NOT EXISTS case_id UUID;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS case_id UUID;

COMMENT ON TABLE saas.intake_case IS 'M01 進線 Case/Inquiry：一次進線事件，上游容器（下含多 problem_card/work_order）。CR-0108';
COMMENT ON COLUMN saas.intake_case.source_channel IS 'D1 Phase I 渠道：line/phone/web/referral（partner 4 渠道 Phase II）';
COMMENT ON COLUMN saas.intake_case.first_response_due_at IS 'D2 建案 + first_response_sla_minutes（暫定 30，入 config 待業主）';
