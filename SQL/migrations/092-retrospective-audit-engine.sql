-- ═══════════════════════════════════════════════════════════════════════════
-- 092-retrospective-audit-engine.sql — 急件事後補審引擎（WBS 1.2.2 / CR-0129）
--
-- 業主裁決（CR-0129 §8，2026-07-09）：
--   D1a 急件加價 NTD 1500 初值（seed URG-01）＋M18 config 可調；
--   D2a 補審完成擋「結案」（completed→confirmed）——完工回報起算 4h 補審窗。
--
-- 設計（15_SDS §4.5）：
--   - quote.audit_due_at：急件單完工回報時寫入（NOW()+窗長，預設 PT4H 讀 M18
--     config emergency_audit_policy.audit_window_hours）。佔位報價本身即補審任務
--     （不建獨立 task 表）；sla_monitor 掃 audit_due_at 逾期 → audit_overdue 告警。
--   - URG-01 急件加價目錄項：小編補審明細帶入；金額可被 M18 config
--     emergency_audit_policy.surcharge_amount 覆蓋（app 層 add_line 特例）。
--   - change_request_type_dim 補 emergency_audit_breach：同租戶連 ≥3 件急件補審
--     逾時 → sla_monitor 自動開 ChangeRequest 進主管佇列（BR-WO-04）。
--
-- 慣例：IF NOT EXISTS / ON CONFLICT DO NOTHING，可重複套用。落庫：品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE quote
    ADD COLUMN IF NOT EXISTS audit_due_at TIMESTAMP WITH TIME ZONE;
COMMENT ON COLUMN quote.audit_due_at IS
    '急件補審截止（CR-0129/15_SDS §4.5）：急件單完工回報時寫 NOW()+PT4H（config 可調）；'
    'NULL=非急件補審單。sla_monitor 掃逾期告警升主管；連 3 件逾時自動開 ChangeRequest';

-- sla_monitor 逾期掃描路徑（audit_due_at 非空且未達 accepted）
CREATE INDEX IF NOT EXISTS idx_quote_audit_due ON quote (audit_due_at) WHERE audit_due_at IS NOT NULL;

-- 急件加價目錄項（D1a：1500 初值；金額調整走 M18 config 覆蓋或目錄治理）
INSERT INTO service_catalog
    (service_code, category, service_name, service_type, unit, needs_dispatch,
     internal_note, internal_base_cost, suggested_customer_price, decision_status, is_mock)
VALUES
    ('URG-01', '急件服務', '急件加價（事後補審）', 'emergency', '次', '否',
     '急件 carve-out 補審明細加價項（CR-0129 D1a 業主定案 1500 初值；15_SDS §4.5 步驟4）',
     0, 1500, '業主已定案', FALSE)
ON CONFLICT (service_code) DO NOTHING;

-- 連 3 逾時自動開 ChangeRequest 的類型碼（BR-WO-04）
INSERT INTO saas.change_request_type_dim (code, category, description) VALUES
    ('emergency_audit_breach', 'governance', '急件補審連續逾時（同租戶連 ≥3 件逾 4h 未補審）——自動開立，主管檢討急件流程')
ON CONFLICT (code) DO NOTHING;
