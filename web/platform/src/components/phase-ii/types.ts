/**
 * web/src/components/phase-ii/types.ts — Phase II 9 FR 共用 type 定義
 *
 * 對應 phase-ii-web-integration-plan §3 (API 共用 types) + §4 (共用 component)。
 * Sprint 1-5 BUILD 時 import 本檔取代分散在各 page 的 inline type 宣告。
 *
 * 與 backend 對應：
 *   - api/services/* 各 service 的 dict response shape
 *   - api/models/generated/ (若已生成 OpenAPI types) 可逐步遷移
 */

// ─────────────────────────────────────────────────────────────────────
// 共用狀態機 (FR-0045/0046/0047 三個 statement 共用)
// ─────────────────────────────────────────────────────────────────────

export type StatementStatus =
  | "draft"
  | "pending_review"
  | "disputed"
  | "approved"
  | "rejected"
  | "paid";

export const STATEMENT_STATUS_VALUES: StatementStatus[] = [
  "draft",
  "pending_review",
  "disputed",
  "approved",
  "rejected",
  "paid",
];

// ─────────────────────────────────────────────────────────────────────
// FR-0049 Approval Inbox
// ─────────────────────────────────────────────────────────────────────

export type ApprovalInboxItemType =
  | "scope_change"
  | "refund"
  | "dispute"
  | "reschedule"
  | "recon_exception";

export type Severity = "high" | "medium" | "low";

export interface ApprovalInboxItem {
  type: ApprovalInboxItemType;
  id: string;
  target_id: string | null;
  summary: string;
  severity: Severity;
  created_at: string | null;
  days_overdue: number;
}

export interface ApprovalInboxResponse {
  tenant_id: string;
  type_filter: string | null;
  total: number;
  by_type: Record<ApprovalInboxItemType, number>;
  items: ApprovalInboxItem[];
}

// ─────────────────────────────────────────────────────────────────────
// FR-0044 Technician Lifecycle
// ─────────────────────────────────────────────────────────────────────

export type TechnicianStatus =
  | "pending_approval"
  | "active"
  | "suspended"
  | "rejected"
  | "terminated"
  | "inactive";

export type TechnicianLifecycleEventType =
  | "onboarding_approved"
  | "onboarding_rejected"
  | "suspended"
  | "reactivated"
  | "terminated"
  | "rating_threshold_breach"
  | "cert_expired";

export interface TechnicianLifecycleEvent {
  id: string;
  technician_id: string;
  event_type: TechnicianLifecycleEventType;
  previous_status: string | null;
  new_status: string | null;
  reason: string;
  notes: string | null;
  actor_user_id: string | null;
  actor_role: string | null;
  created_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0045 Technician AP Statement
// ─────────────────────────────────────────────────────────────────────

export interface TechStatement {
  id: string;
  tenant_id: string;
  technician_id: string;
  period_year: number;
  period_month: number;
  total_completed_orders: number;
  gross_amount: string;          // decimal string e.g. "50000.00"
  travel_fee_deduction: string;
  cash_collection_deduction: string;
  dispute_hold_amount: string;
  other_deductions: string;
  net_amount: string;
  status: StatementStatus;
  dispute_window_ends_at: string | null;
  disputed_at: string | null;
  dispute_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  paid_at: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0046 Dispatcher Commission Statement
// ─────────────────────────────────────────────────────────────────────

export interface DispatcherCommissionStatement {
  id: string;
  tenant_id: string;
  dispatcher_user_id: string;
  period_year: number;
  period_month: number;
  total_dispatched_orders: number;
  total_completed_orders: number;
  completion_rate_pct: string;
  avg_customer_satisfaction: number | null;
  base_commission: string;
  performance_bonus: string;
  penalty: string;
  net_commission: string;
  status: StatementStatus;
  // ... (其他狀態機欄位同 TechStatement)
  dispute_window_ends_at: string | null;
  disputed_at: string | null;
  dispute_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  paid_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0047 Brand B2B Settlement
// ─────────────────────────────────────────────────────────────────────

export type B2BDirection = "AR" | "AP" | "NET";

export type B2BPayableTo = "brand" | "platform" | null;

export interface BrandB2BStatement {
  id: string;
  tenant_id: string;
  brand_partner_id: string;
  brand_name: string;
  contract_ref: string | null;
  period_year: number;
  period_month: number;
  direction: B2BDirection;
  total_service_orders: number;
  total_warranty_claims: number;
  sla_breach_count: number;
  ar_service_fee: string;
  ap_commission: string;
  warranty_deduction: string;
  sla_penalty: string;
  net_amount: string;
  net_payable_to: B2BPayableTo;
  status: StatementStatus;
  // ... (其他狀態機欄位)
  dispute_window_ends_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  paid_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0053 GDPR Forget Request
// ─────────────────────────────────────────────────────────────────────

export type GdprForgetStatus =
  | "received"
  | "legal_hold_denied"
  | "soft_deleted"
  | "hard_deleted"
  | "cancelled";

export type GdprForgetRequestedBy = "customer_self" | "admin" | "dpo";

export interface GdprForgetRequest {
  id: string;
  tenant_id: string;
  subject_user_id: string;
  subject_email: string | null;
  status: GdprForgetStatus;
  requested_by: GdprForgetRequestedBy;
  legal_hold_reason: string | null;
  expected_release_at: string | null;
  received_at: string | null;
  soft_deleted_at: string | null;
  hard_delete_eligible_at: string | null;
  hard_deleted_at: string | null;
  actor_user_id: string | null;
  notes: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0050 AI Governance Trace
// ─────────────────────────────────────────────────────────────────────

export type AiDecisionType =
  | "reasoning"
  | "tool_call"
  | "output"
  | "guardrail_block"
  | "human_handoff";

export type GuardrailAction = "block" | "warn" | "redact" | "allow";

export interface AiDecisionTrace {
  id: string;
  decision_type: AiDecisionType;
  conversation_id: string | null;
  work_order_id: string | null;
  agent_session_id: string | null;
  prd_source: string | null;
  charter_rule: string | null;
  owner_decision_ref: string | null;
  action_summary: string;
  guardrail_triggered: string | null;
  guardrail_action: GuardrailAction | null;
  agent_version: string | null;
  created_at: string | null;
}

export interface AiGovernanceSummary {
  tenant_id: string;
  window: { start_date: string | null; end_date: string | null };
  totals: {
    total_decisions: number;
    block_count: number;
    block_rate_pct: number;
  };
  by_decision_type: Partial<Record<AiDecisionType, number>>;
  by_guardrail_action: Partial<Record<GuardrailAction, number>>;
  by_agent_version: Record<string, number>;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0051 SOP Feedback
// ─────────────────────────────────────────────────────────────────────

export type SopFeedbackSource =
  | "customer_thumbs"
  | "technician_onsite"
  | "rma_finding"
  | "ai_eval"
  | "csm_manual";

export type SopSentiment = "positive" | "neutral" | "negative";

export type SopType = "draft" | "case_entry";

export interface SopFeedbackItem {
  id: string;
  sop_id: string;
  sop_type: SopType;
  source: SopFeedbackSource;
  sentiment: SopSentiment;
  score: number | null;
  comment: string | null;
  reporter_user_id: string | null;
  work_order_id: string | null;
  created_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0048 RMA Quality Finding
// ─────────────────────────────────────────────────────────────────────

export type AiDiagnosisAccuracy = "accurate" | "partial" | "wrong";

export interface RmaQualityFinding {
  id: string;
  warranty_claim_id: string | null;
  work_order_id: string | null;
  technician_id: string | null;
  brand: string | null;
  device_model: string | null;
  failure_mode: string;
  root_cause: string | null;
  is_repeat_failure: boolean;
  brand_quality_score: number | null;
  technician_quality_score: number | null;
  ai_diagnosis_accuracy: AiDiagnosisAccuracy | null;
  customer_satisfaction_score: number | null;
  created_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// 共用 Lifespan Monitor Health (ops dashboard)
// ─────────────────────────────────────────────────────────────────────

export type MonitorState =
  | "running"
  | "stopping"
  | "crashed"
  | "not_started"
  | "import_error";

export interface MonitorStatus {
  state: MonitorState;
  interval_seconds?: number;
  task_started?: boolean;
  task_done?: boolean | null;
  stopping_signal?: boolean | null;
  error?: string;
}

export interface LifespanMonitorsHealth {
  monitors: Record<string, MonitorStatus>;
  summary: {
    total: number;
    by_state: Partial<Record<MonitorState, number>>;
    all_running: boolean;
  };
}
