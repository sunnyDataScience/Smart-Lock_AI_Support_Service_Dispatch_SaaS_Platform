-- ============================================================================
-- Schema_doc_numbering.sql — ERP 業務單據編號 (document_number) 統一機制
-- ============================================================================
--
-- 對應 ADR-009 §8 D3 拍板：5 條 P0 業務單據加 human-readable 編號。
--
-- 編號格式: {prefix}-{YYYYMMDD}-{NNNN}
--   ST  = ServiceTicket (conversations)
--   WO  = WorkOrder    (work_orders)
--   RM  = RefundMemo   (refund_requests)
--   WC  = WarrantyClaim (warranty_claims)
--   SOP = SopDraft     (sop_drafts)
--
-- 序號採全域遞增（NEXTVAL on shared sequence），非每日 reset；
-- 1 年 100 萬筆才需擴展到 5 位 padding。
--
-- 套用方式: psql ... -f SQL/Schema_doc_numbering.sql
-- 既存 row 的 document_number 為 NULL（後續可批次 backfill PR）。
-- ============================================================================

-- ── 1. Sequences（每業務單據一個獨立 sequence）──
CREATE SEQUENCE IF NOT EXISTS doc_seq_st;   -- ServiceTicket
CREATE SEQUENCE IF NOT EXISTS doc_seq_wo;   -- WorkOrder
CREATE SEQUENCE IF NOT EXISTS doc_seq_rm;   -- RefundMemo
CREATE SEQUENCE IF NOT EXISTS doc_seq_wc;   -- WarrantyClaim
CREATE SEQUENCE IF NOT EXISTS doc_seq_sop;  -- SopDraft

-- ── 2. 統一 generation function ──
-- 用法: SELECT generate_doc_number('RM', 'doc_seq_rm');
-- 回傳: 'RM-20260509-0042'
CREATE OR REPLACE FUNCTION generate_doc_number(prefix TEXT, seq_name TEXT)
RETURNS TEXT AS $$
DECLARE
    seq_val BIGINT;
BEGIN
    EXECUTE format('SELECT NEXTVAL(%L)', seq_name) INTO seq_val;
    RETURN prefix || '-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
           LPAD(seq_val::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_doc_number(TEXT, TEXT) IS
'ERP-style document number generator (ADR-009 §8 D3). Format: {prefix}-{YYYYMMDD}-{NNNN}';

-- ── 3. 5 表加 document_number 欄位 ──
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(30) UNIQUE;
COMMENT ON COLUMN conversations.document_number IS
'ServiceTicket 編號 (ST-YYYYMMDD-NNNN)，給客戶引用用';

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(30) UNIQUE;
COMMENT ON COLUMN work_orders.document_number IS
'WorkOrder 編號 (WO-YYYYMMDD-NNNN)';

ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(30) UNIQUE;
COMMENT ON COLUMN refund_requests.document_number IS
'RefundMemo 編號 (RM-YYYYMMDD-NNNN)';

ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(30) UNIQUE;
COMMENT ON COLUMN warranty_claims.document_number IS
'WarrantyClaim 編號 (WC-YYYYMMDD-NNNN)';

ALTER TABLE sop_drafts
    ADD COLUMN IF NOT EXISTS document_number VARCHAR(30) UNIQUE;
COMMENT ON COLUMN sop_drafts.document_number IS
'SopDraft 編號 (SOP-YYYYMMDD-NNNN)';

-- ── 4. agent_outbox 表（D pattern 失敗 fallback；worker 留 phase 2）──
CREATE TABLE IF NOT EXISTS agent_outbox (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id     VARCHAR(50) NOT NULL,
                                -- 'F-001-conv' / 'F-001-pc' / 'F-014-refund' / etc.
    endpoint    TEXT NOT NULL,  -- /api/v1/conversations
    payload     JSONB NOT NULL,
    headers     JSONB,          -- 含 Idempotency-Key
    attempts    INT NOT NULL DEFAULT 0,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
                                -- 'pending' / 'processing' / 'failed' / 'succeeded'
    last_error  TEXT,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_outbox_status_created
    ON agent_outbox (status, created_at)
    WHERE status IN ('pending', 'processing');

COMMENT ON TABLE agent_outbox IS
'D pattern HTTP-call 失敗 fallback。worker 掃 pending 重試（phase 2 補實作）。';

-- ── 5. 業務 unique key 欄位（ADR-009 §8 idempotency layer 2）──

-- F-014 RefundRequest: 業務 key (work_order_id, reason_code)
ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS reason_code VARCHAR(50);
COMMENT ON COLUMN refund_requests.reason_code IS
'退款原因分類碼（業務 unique key 一部分）：defective_product / service_quality / customer_dissatisfaction / billing_error / other';

ALTER TABLE refund_requests
    ADD COLUMN IF NOT EXISTS requested_by_role VARCHAR(50);
COMMENT ON COLUMN refund_requests.requested_by_role IS
'觸發路徑 (dual-trigger 區分)：customer_via_line / customer_service / manager';

CREATE UNIQUE INDEX IF NOT EXISTS uniq_refund_wo_reason_active
    ON refund_requests (work_order_id, reason_code)
    WHERE status NOT IN ('rejected', 'cancelled');

-- F-015 WarrantyClaim: 業務 key (work_order_id, claim_type)
ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS claim_type VARCHAR(50);
COMMENT ON COLUMN warranty_claims.claim_type IS
'保固申訴類型（業務 unique key 一部分）：defective / malfunction / premature_failure / missing_parts / other';

ALTER TABLE warranty_claims
    ADD COLUMN IF NOT EXISTS requested_by_role VARCHAR(50);
COMMENT ON COLUMN warranty_claims.requested_by_role IS
'觸發路徑 (dual-trigger 區分)：customer_via_line / customer_service / technician';

CREATE UNIQUE INDEX IF NOT EXISTS uniq_warranty_wo_type_active
    ON warranty_claims (work_order_id, claim_type)
    WHERE status NOT IN ('rejected', 'closed') AND work_order_id IS NOT NULL;

-- F-017 SopDraft: 業務 key (case_entry_id 或 source_problem_card_id, model_version)
ALTER TABLE sop_drafts
    ADD COLUMN IF NOT EXISTS model_version VARCHAR(50);
COMMENT ON COLUMN sop_drafts.model_version IS
'產生此 draft 的 LLM 模型 + 版本（業務 unique key 一部分，允許同案不同版本）';

ALTER TABLE sop_drafts
    ADD COLUMN IF NOT EXISTS confidence_score FLOAT;
COMMENT ON COLUMN sop_drafts.confidence_score IS
'LLM extract 信心分數 (0.0~1.0)';

CREATE UNIQUE INDEX IF NOT EXISTS uniq_sop_pc_model
    ON sop_drafts (source_problem_card_id, model_version)
    WHERE source_problem_card_id IS NOT NULL AND model_version IS NOT NULL;
