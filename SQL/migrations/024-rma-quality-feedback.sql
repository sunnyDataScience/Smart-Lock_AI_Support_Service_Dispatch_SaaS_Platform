-- ============================================================================
-- 024-rma-quality-feedback.sql — FR-0048 Phase II MVP: RMA Quality Feedback Loop
-- ============================================================================
-- 目的：RMA 結案後品質訊號回收 → 4 cascade：品牌商 / 技師績效 / SOP / commission。
--
-- 對齊 FR-0048 §1 closed loop quality system。
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.rma_quality_finding (
  id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               uuid        NOT NULL REFERENCES saas.tenant(id),

  -- 關聯 RMA / Warranty case
  warranty_claim_id       uuid        NULL,   -- FR-0015 warranty_claims.id
  work_order_id           uuid        NULL,   -- 對應工單
  technician_id           uuid        NULL,   -- 處理技師
  brand                   text        NULL,   -- 品牌商（給 brand feedback）
  device_model            text        NULL,

  -- 品質訊號 (FR-0048 §1 4 cascade 對應)
  failure_mode            text        NOT NULL,    -- e.g. 'battery_drain' / 'motor_jam' / 'firmware_bug'
  root_cause              text        NULL,        -- 根因（技師現場判斷）
  is_repeat_failure       boolean     NOT NULL DEFAULT false,  -- 是否重複故障（30 天內）

  -- 4 cascade 評分（1-5 各維度）
  brand_quality_score     numeric(3,1) NULL CHECK (brand_quality_score IS NULL OR brand_quality_score BETWEEN 1.0 AND 5.0),
  technician_quality_score numeric(3,1) NULL CHECK (technician_quality_score IS NULL OR technician_quality_score BETWEEN 1.0 AND 5.0),
  ai_diagnosis_accuracy   text        NULL CHECK (ai_diagnosis_accuracy IS NULL OR ai_diagnosis_accuracy IN ('accurate', 'partial', 'wrong')),
  customer_satisfaction_score numeric(3,1) NULL CHECK (customer_satisfaction_score IS NULL OR customer_satisfaction_score BETWEEN 1.0 AND 5.0),

  -- audit
  reported_by_user_id     uuid        NULL,
  notes                   text        NULL,

  created_at              timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS rma_q_tenant_created_idx
  ON saas.rma_quality_finding(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS rma_q_failure_mode_idx
  ON saas.rma_quality_finding(failure_mode, created_at DESC);

CREATE INDEX IF NOT EXISTS rma_q_brand_idx
  ON saas.rma_quality_finding(brand, created_at DESC)
  WHERE brand IS NOT NULL;

CREATE INDEX IF NOT EXISTS rma_q_technician_idx
  ON saas.rma_quality_finding(technician_id, created_at DESC)
  WHERE technician_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS rma_q_warranty_idx
  ON saas.rma_quality_finding(warranty_claim_id)
  WHERE warranty_claim_id IS NOT NULL;

COMMENT ON TABLE saas.rma_quality_finding IS
  'FR-0048 RMA Quality Feedback Loop：每筆 RMA 結案後品質訊號，'
  '4 cascade：brand_quality / technician_quality / ai_diagnosis_accuracy / '
  'customer_satisfaction，給 §1 closed loop quality system 用';
