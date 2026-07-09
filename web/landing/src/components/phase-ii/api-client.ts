/**
 * web/src/components/phase-ii/api-client.ts — Phase II 9 FR API client
 *
 * Sprint 1-5 BUILD 時 import 統一 fetch wrapper，集中：
 *   - tenant-scoped URL 構造 (/tenants/{tid}/...)
 *   - auth header 注入
 *   - JSON 解析 + error normalize
 *   - query string 構造
 *
 * 對齊 phase-ii-web-integration-plan §3「API 共用 types」+ backend
 * 9 service router (v2 tenant-scoped)。
 */

import type {
  ApprovalInboxResponse,
  ApprovalInboxItemType,
  TechnicianLifecycleEvent,
  TechStatement,
  DispatcherCommissionStatement,
  BrandB2BStatement,
  GdprForgetRequest,
  GdprForgetStatus,
  AiDecisionTrace,
  AiGovernanceSummary,
  SopFeedbackItem,
  RmaQualityFinding,
  LifespanMonitorsHealth,
} from "./types";

// ─────────────────────────────────────────────────────────────────────
// 基礎 client + error
// ─────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface ClientOptions {
  baseUrl: string;          // e.g. "https://api.example.com" or "/api"
  tenantId: string;         // current tenant
  getAuthToken: () => string | Promise<string>;
  fetchImpl?: typeof fetch; // for testing
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
}

async function _request<T>(
  opts: ClientOptions,
  path: string,
  req: RequestOptions = {},
): Promise<T> {
  const fetchFn = opts.fetchImpl ?? fetch;
  const token = await opts.getAuthToken();

  let url = `${opts.baseUrl}${path}`;
  if (req.query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(req.query)) {
      if (v === undefined || v === null) continue;
      params.append(k, String(v));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const res = await fetchFn(url, {
    method: req.method ?? "GET",
    headers,
    body: req.body ? JSON.stringify(req.body) : undefined,
  });

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, `API ${res.status} ${path}`, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ─────────────────────────────────────────────────────────────────────
// FR-0049 Approval Inbox
// ─────────────────────────────────────────────────────────────────────

export const approvalInbox = {
  list: (opts: ClientOptions, query?: {
    type?: ApprovalInboxItemType;
    limit?: number;
  }) =>
    _request<ApprovalInboxResponse>(
      opts,
      `/tenants/${opts.tenantId}/approval-inbox`,
      { query },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0044 Technician Lifecycle
// ─────────────────────────────────────────────────────────────────────

export const technicianLifecycle = {
  approve: (
    opts: ClientOptions,
    technicianId: string,
    body: { reason: string; notes?: string },
  ) =>
    _request<TechnicianLifecycleEvent>(
      opts,
      `/tenants/${opts.tenantId}/technicians/${technicianId}/approve`,
      { method: "POST", body },
    ),
  reject: (
    opts: ClientOptions,
    technicianId: string,
    body: { reason: string; notes?: string },
  ) =>
    _request<TechnicianLifecycleEvent>(
      opts,
      `/tenants/${opts.tenantId}/technicians/${technicianId}/reject`,
      { method: "POST", body },
    ),
  suspend: (
    opts: ClientOptions,
    technicianId: string,
    body: { reason: string; notes?: string },
  ) =>
    _request<TechnicianLifecycleEvent>(
      opts,
      `/tenants/${opts.tenantId}/technicians/${technicianId}/suspend`,
      { method: "POST", body },
    ),
  reactivate: (
    opts: ClientOptions,
    technicianId: string,
    body: { reason: string; notes?: string },
  ) =>
    _request<TechnicianLifecycleEvent>(
      opts,
      `/tenants/${opts.tenantId}/technicians/${technicianId}/reactivate`,
      { method: "POST", body },
    ),
  terminate: (
    opts: ClientOptions,
    technicianId: string,
    body: { reason: string; notes?: string },
  ) =>
    _request<TechnicianLifecycleEvent>(
      opts,
      `/tenants/${opts.tenantId}/technicians/${technicianId}/terminate`,
      { method: "POST", body },
    ),
  events: (
    opts: ClientOptions,
    technicianId: string,
    query?: { limit?: number },
  ) =>
    _request<TechnicianLifecycleEvent[]>(
      opts,
      `/tenants/${opts.tenantId}/technicians/${technicianId}/lifecycle-events`,
      { query },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0045 Technician Statement
// ─────────────────────────────────────────────────────────────────────

export const techStatement = {
  myStatements: (
    opts: ClientOptions,
    query?: { period_year?: number; period_month?: number },
  ) =>
    _request<TechStatement[]>(
      opts,
      `/tenants/${opts.tenantId}/me/statements`,
      { query },
    ),
  dispute: (
    opts: ClientOptions,
    statementId: string,
    body: { dispute_reason: string },
  ) =>
    _request<TechStatement>(
      opts,
      `/tenants/${opts.tenantId}/statements/${statementId}/dispute`,
      { method: "POST", body },
    ),
  approve: (opts: ClientOptions, statementId: string) =>
    _request<TechStatement>(
      opts,
      `/tenants/${opts.tenantId}/statements/${statementId}/approve`,
      { method: "POST" },
    ),
  pay: (opts: ClientOptions, statementId: string) =>
    _request<TechStatement>(
      opts,
      `/tenants/${opts.tenantId}/statements/${statementId}/pay`,
      { method: "POST" },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0046 Dispatcher Commission Statement
// ─────────────────────────────────────────────────────────────────────

export const dispatcherCommission = {
  myStatements: (
    opts: ClientOptions,
    query?: { period_year?: number; period_month?: number },
  ) =>
    _request<DispatcherCommissionStatement[]>(
      opts,
      `/tenants/${opts.tenantId}/me/commission-statements`,
      { query },
    ),
  dispute: (
    opts: ClientOptions,
    statementId: string,
    body: { dispute_reason: string },
  ) =>
    _request<DispatcherCommissionStatement>(
      opts,
      `/tenants/${opts.tenantId}/commission-statements/${statementId}/dispute`,
      { method: "POST", body },
    ),
  approve: (opts: ClientOptions, statementId: string) =>
    _request<DispatcherCommissionStatement>(
      opts,
      `/tenants/${opts.tenantId}/commission-statements/${statementId}/approve`,
      { method: "POST" },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0047 Brand B2B Settlement
// ─────────────────────────────────────────────────────────────────────

export const brandB2B = {
  list: (
    opts: ClientOptions,
    query?: {
      period_year?: number;
      period_month?: number;
      direction?: "AR" | "AP" | "NET";
      status?: string;
    },
  ) =>
    _request<BrandB2BStatement[]>(
      opts,
      `/tenants/${opts.tenantId}/brand-b2b-statements`,
      { query },
    ),
  approve: (opts: ClientOptions, statementId: string) =>
    _request<BrandB2BStatement>(
      opts,
      `/tenants/${opts.tenantId}/brand-b2b-statements/${statementId}/approve`,
      { method: "POST" },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0053 GDPR
// ─────────────────────────────────────────────────────────────────────

export const gdprForget = {
  list: (
    opts: ClientOptions,
    query?: { status?: GdprForgetStatus; limit?: number },
  ) =>
    _request<GdprForgetRequest[]>(
      opts,
      `/tenants/${opts.tenantId}/gdpr/forget-requests`,
      { query },
    ),
  receive: (
    opts: ClientOptions,
    body: {
      subject_user_id: string;
      subject_email?: string;
      requested_by: "customer_self" | "admin" | "dpo";
      notes?: string;
    },
  ) =>
    _request<GdprForgetRequest>(
      opts,
      `/tenants/${opts.tenantId}/gdpr/forget-requests/receive`,
      { method: "POST", body },
    ),
  legalHold: (
    opts: ClientOptions,
    requestId: string,
    body: { legal_hold_reason: string; expected_release_at?: string },
  ) =>
    _request<GdprForgetRequest>(
      opts,
      `/tenants/${opts.tenantId}/gdpr/forget-requests/${requestId}/legal-hold`,
      { method: "POST", body },
    ),
  softDelete: (opts: ClientOptions, requestId: string) =>
    _request<GdprForgetRequest>(
      opts,
      `/tenants/${opts.tenantId}/gdpr/forget-requests/${requestId}/soft-delete`,
      { method: "POST" },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0050 AI Governance
// ─────────────────────────────────────────────────────────────────────

export const aiGovernance = {
  traces: (
    opts: ClientOptions,
    query?: {
      decision_type?: string;
      conversation_id?: string;
      work_order_id?: string;
      from?: string;
      to?: string;
      limit?: number;
    },
  ) =>
    _request<AiDecisionTrace[]>(
      opts,
      `/tenants/${opts.tenantId}/ai/governance/traces`,
      { query },
    ),
  summary: (
    opts: ClientOptions,
    query?: { from?: string; to?: string },
  ) =>
    _request<AiGovernanceSummary>(
      opts,
      `/tenants/${opts.tenantId}/ai/governance/summary`,
      { query },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0051 SOP Feedback
// ─────────────────────────────────────────────────────────────────────

export const sopFeedback = {
  list: (
    opts: ClientOptions,
    query?: {
      sop_id?: string;
      sop_type?: "draft" | "case_entry";
      sentiment?: "positive" | "neutral" | "negative";
      limit?: number;
    },
  ) =>
    _request<SopFeedbackItem[]>(
      opts,
      `/tenants/${opts.tenantId}/sop-feedback`,
      { query },
    ),
  submit: (
    opts: ClientOptions,
    body: {
      sop_id: string;
      sop_type: "draft" | "case_entry";
      source: string;
      sentiment: "positive" | "neutral" | "negative";
      score?: number;
      comment?: string;
      work_order_id?: string;
    },
  ) =>
    _request<SopFeedbackItem>(
      opts,
      `/tenants/${opts.tenantId}/sop-feedback`,
      { method: "POST", body },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// FR-0048 RMA Quality
// ─────────────────────────────────────────────────────────────────────

export const rmaQuality = {
  findings: (
    opts: ClientOptions,
    query?: {
      brand?: string;
      device_model?: string;
      failure_mode?: string;
      is_repeat_failure?: boolean;
      limit?: number;
    },
  ) =>
    _request<RmaQualityFinding[]>(
      opts,
      `/tenants/${opts.tenantId}/rma/quality-findings`,
      { query },
    ),
};

// ─────────────────────────────────────────────────────────────────────
// Ops Monitor Health (lifespan dashboard)
// ─────────────────────────────────────────────────────────────────────

export const opsHealth = {
  monitors: (opts: ClientOptions) =>
    _request<LifespanMonitorsHealth>(opts, `/ops/lifespan-monitors`),
};

// ─────────────────────────────────────────────────────────────────────
// 共用 namespace (給 import { PhaseIIApi } from "..." 用)
// ─────────────────────────────────────────────────────────────────────

export const PhaseIIApi = {
  approvalInbox,
  technicianLifecycle,
  techStatement,
  dispatcherCommission,
  brandB2B,
  gdprForget,
  aiGovernance,
  sopFeedback,
  rmaQuality,
  opsHealth,
};
