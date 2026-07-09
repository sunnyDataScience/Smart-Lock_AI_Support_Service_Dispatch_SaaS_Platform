/**
 * web/src/components/phase-ii/labels.ts — Phase II 9 FR 共用 label/color 字典
 *
 * Sprint 1-5 BUILD 時 import 統一 label 翻譯與 badge color，避免分散 hardcode。
 * 對應 backend enum 字串值對外顯示的繁中 label。
 *
 * 用法：
 *   import { STATEMENT_STATUS_LABEL, STATEMENT_STATUS_COLOR } from "...";
 *   <Badge color={STATEMENT_STATUS_COLOR[s.status]}>
 *     {STATEMENT_STATUS_LABEL[s.status]}
 *   </Badge>
 */

import type {
  StatementStatus,
  ApprovalInboxItemType,
  Severity,
  TechnicianStatus,
  TechnicianLifecycleEventType,
  B2BDirection,
  GdprForgetStatus,
  GdprForgetRequestedBy,
  AiDecisionType,
  GuardrailAction,
  SopFeedbackSource,
  SopSentiment,
  SopType,
  AiDiagnosisAccuracy,
  MonitorState,
} from "./types";

// ─────────────────────────────────────────────────────────────────────
// Color 統一 palette (對齊 Tailwind / shadcn badge variants)
// ─────────────────────────────────────────────────────────────────────

export type BadgeColor =
  | "gray"
  | "blue"
  | "yellow"
  | "orange"
  | "red"
  | "green"
  | "purple";

// ─────────────────────────────────────────────────────────────────────
// Statement Status (FR-0045/0046/0047 三個 statement 共用)
// ─────────────────────────────────────────────────────────────────────

export const STATEMENT_STATUS_LABEL: Record<StatementStatus, string> = {
  draft: "草稿",
  pending_review: "待覆核",
  disputed: "申訴中",
  approved: "已核准",
  rejected: "已駁回",
  paid: "已支付",
};

export const STATEMENT_STATUS_COLOR: Record<StatementStatus, BadgeColor> = {
  draft: "gray",
  pending_review: "yellow",
  disputed: "orange",
  approved: "blue",
  rejected: "red",
  paid: "green",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0049 Approval Inbox
// ─────────────────────────────────────────────────────────────────────

export const APPROVAL_INBOX_TYPE_LABEL: Record<ApprovalInboxItemType, string> = {
  scope_change: "範圍變更",
  refund: "退款",
  dispute: "申訴",
  reschedule: "改期",
  recon_exception: "對帳例外",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export const SEVERITY_COLOR: Record<Severity, BadgeColor> = {
  high: "red",
  medium: "orange",
  low: "yellow",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0044 Technician Lifecycle
// ─────────────────────────────────────────────────────────────────────

export const TECHNICIAN_STATUS_LABEL: Record<TechnicianStatus, string> = {
  pending_approval: "待審核",
  active: "在職",
  suspended: "停權",
  rejected: "未通過",
  terminated: "終止",
  inactive: "離職",
};

export const TECHNICIAN_STATUS_COLOR: Record<TechnicianStatus, BadgeColor> = {
  pending_approval: "yellow",
  active: "green",
  suspended: "orange",
  rejected: "red",
  terminated: "red",
  inactive: "gray",
};

export const TECHNICIAN_LIFECYCLE_EVENT_LABEL: Record<
  TechnicianLifecycleEventType,
  string
> = {
  onboarding_approved: "入職核准",
  onboarding_rejected: "入職駁回",
  suspended: "停權",
  reactivated: "復權",
  terminated: "終止合作",
  rating_threshold_breach: "評分破閾值",
  cert_expired: "證照過期",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0047 B2B Direction
// ─────────────────────────────────────────────────────────────────────

export const B2B_DIRECTION_LABEL: Record<B2BDirection, string> = {
  AR: "應收",
  AP: "應付",
  NET: "淨額",
};

export const B2B_DIRECTION_COLOR: Record<B2BDirection, BadgeColor> = {
  AR: "blue",
  AP: "orange",
  NET: "purple",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0053 GDPR
// ─────────────────────────────────────────────────────────────────────

export const GDPR_FORGET_STATUS_LABEL: Record<GdprForgetStatus, string> = {
  received: "已收件",
  legal_hold_denied: "法務扣留",
  soft_deleted: "已軟刪",
  hard_deleted: "已硬刪",
  cancelled: "已取消",
};

export const GDPR_FORGET_STATUS_COLOR: Record<GdprForgetStatus, BadgeColor> = {
  received: "yellow",
  legal_hold_denied: "red",
  soft_deleted: "blue",
  hard_deleted: "gray",
  cancelled: "gray",
};

export const GDPR_REQUESTED_BY_LABEL: Record<GdprForgetRequestedBy, string> = {
  customer_self: "客戶自請",
  admin: "管理員",
  dpo: "DPO",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0050 AI Governance
// ─────────────────────────────────────────────────────────────────────

export const AI_DECISION_TYPE_LABEL: Record<AiDecisionType, string> = {
  reasoning: "推理",
  tool_call: "工具呼叫",
  output: "輸出",
  guardrail_block: "安全防護阻擋",
  human_handoff: "轉接人工",
};

export const GUARDRAIL_ACTION_LABEL: Record<GuardrailAction, string> = {
  block: "阻擋",
  warn: "警示",
  redact: "去識別",
  allow: "放行",
};

export const GUARDRAIL_ACTION_COLOR: Record<GuardrailAction, BadgeColor> = {
  block: "red",
  warn: "orange",
  redact: "purple",
  allow: "green",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0051 SOP Feedback
// ─────────────────────────────────────────────────────────────────────

export const SOP_FEEDBACK_SOURCE_LABEL: Record<SopFeedbackSource, string> = {
  customer_thumbs: "客戶評分",
  technician_onsite: "技師現場回報",
  rma_finding: "RMA 發現",
  ai_eval: "AI 評估",
  csm_manual: "CSM 手動",
};

export const SOP_SENTIMENT_LABEL: Record<SopSentiment, string> = {
  positive: "正向",
  neutral: "中性",
  negative: "負向",
};

export const SOP_SENTIMENT_COLOR: Record<SopSentiment, BadgeColor> = {
  positive: "green",
  neutral: "gray",
  negative: "red",
};

export const SOP_TYPE_LABEL: Record<SopType, string> = {
  draft: "草稿",
  case_entry: "案例條目",
};

// ─────────────────────────────────────────────────────────────────────
// FR-0048 RMA Quality
// ─────────────────────────────────────────────────────────────────────

export const AI_DIAGNOSIS_ACCURACY_LABEL: Record<AiDiagnosisAccuracy, string> = {
  accurate: "正確",
  partial: "部分正確",
  wrong: "錯誤",
};

export const AI_DIAGNOSIS_ACCURACY_COLOR: Record<AiDiagnosisAccuracy, BadgeColor> = {
  accurate: "green",
  partial: "yellow",
  wrong: "red",
};

// ─────────────────────────────────────────────────────────────────────
// Ops monitors (lifespan health dashboard)
// ─────────────────────────────────────────────────────────────────────

export const MONITOR_STATE_LABEL: Record<MonitorState, string> = {
  running: "運作中",
  stopping: "停止中",
  crashed: "已當機",
  not_started: "未啟動",
  import_error: "載入失敗",
};

export const MONITOR_STATE_COLOR: Record<MonitorState, BadgeColor> = {
  running: "green",
  stopping: "yellow",
  crashed: "red",
  not_started: "gray",
  import_error: "red",
};

// ─────────────────────────────────────────────────────────────────────
// 共用 helpers
// ─────────────────────────────────────────────────────────────────────

/**
 * 把 decimal string 轉成人類可讀金額顯示。
 * 範例：formatDecimal("50000.00") → "NT$ 50,000"
 */
export function formatDecimal(value: string, currency = "NT$"): string {
  const num = Number(value);
  if (Number.isNaN(num)) return `${currency} ${value}`;
  return `${currency} ${num.toLocaleString("zh-TW", {
    maximumFractionDigits: 0,
  })}`;
}

/**
 * 把 ISO datetime string 轉本地短格式。
 * 範例：formatDateTime("2026-06-05T12:34:56Z") → "2026/06/05 12:34"
 */
export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * 計算申訴 window 剩多少天 (FR-0045/0046/0047 dispute_window_ends_at)。
 * 負值表已過期。
 */
export function daysUntilDeadline(deadlineIso: string | null): number | null {
  if (!deadlineIso) return null;
  const d = new Date(deadlineIso).getTime();
  if (Number.isNaN(d)) return null;
  const ms = d - Date.now();
  return Math.ceil(ms / (24 * 60 * 60 * 1000));
}
