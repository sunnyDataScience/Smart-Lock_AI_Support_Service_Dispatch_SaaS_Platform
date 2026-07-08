"use client";

import { notFound } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, X } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { UAT_HIDE_FAKE_FLOWS } from "@shared/lib/uatFlags";
import RefundReviewTable from "@/components/admin/RefundReviewTable";
import WorkOrderPicker from "@/components/quotes/WorkOrderPicker";
import { ApiError, api, getCurrentSession, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@shared/hooks/usePaginatedFetch";
import type { components } from "@shared/types/api.generated";

type RefundRequest = components["schemas"]["RefundRequest"];
type RefundRequestEnvelope = components["schemas"]["RefundRequestEnvelope"];
type RefundDecisionBody = components["schemas"]["RefundDecision"];
type Decision = "approve" | "reject" | "escalate";

/**
 * refund_class — 新 SoD 端點（POST /tenants/{tenantId}/refunds）必填欄位，
 * 取代舊 reason_code。tier 由伺服器從 amount 推算（門檻 1k/5k/30k/100k → L1..L5）。
 */
type RefundClass = "product" | "labor" | "material" | "travel" | "inspection";

const REFUND_CLASSES: { value: RefundClass; label: string }[] = [
  { value: "product", label: "商品" },
  { value: "labor", label: "工資" },
  { value: "material", label: "材料" },
  { value: "travel", label: "車馬費" },
  { value: "inspection", label: "檢測費" },
];

/** 覆核主管下拉用：後台員工選項（取自 GET /api/v1/staff，排除發起人）。 */
interface StaffOption {
  id: string;
  name: string;
  role: string;
}

// 角色中文標籤（對齊 /admin/staff 頁 ROLE_LABEL / 後端 _STAFF_ROLES）。
const STAFF_ROLE_LABEL: Record<string, string> = {
  operations_manager: "營運主管",
  dispatcher: "派工員",
  customer_service: "客服",
  reviewer: "審核員",
  admin: "系統管理員",
};

/**
 * 新 SoD 端點回應 data 形狀（尚未進 openapi 生成型別，先在頁面本地定義）。
 * ADR-0040v2 / FR-0014：tenant-scoped + 三維 SoD + 5-tier。
 */
interface SoDRefundResult {
  refund_id: string;
  work_order_id: string;
  amount: number;
  tier: string;
  refund_class: RefundClass;
  state: string;
  initiator_user_id: string;
  approver_user_ids: string[];
  executor_user_id: string | null;
  audit_event_id: string;
}

const SLA_TIER_2H_MS = 2 * 60 * 60 * 1000;
const SLA_TIER_8H_MS = 8 * 60 * 60 * 1000;

function isOpenForReview(status: RefundRequest["status"]): boolean {
  return status === "pending" || status === "escalated";
}

function formatActionError(e: unknown): string {
  return friendlyError(e);
}

export default function RefundReviewPage() {
  // UAT 隱藏(20260702 決議 7):退款審批鏈是真狀態機(DB/SoD/稽核)但金流 0 接通,
  // 核准/執行不會真的退錢 → UAT 期間整頁 404(直接輸入網址也擋),code 保留待金流接通。
  if (UAT_HIDE_FAKE_FLOWS) notFound();
  return <RefundReviewPageInner />;
}

function RefundReviewPageInner() {
  const t = useTranslations("admin.refunds");
  const tc = useTranslations("admin.common");
  const {
    items,
    cursor: nextCursor,
    hasMore,
    lastFetchedAt: updatedAt,
    loading,
    error,
    loadMore,
    refresh: fetchRefunds,
    mutate,
  } = usePaginatedFetch<RefundRequest>({
    // CR-0009 step-extend：refunds_v2 補 listRefundsV2 endpoint 後可遷 v2
    path: tenantPath("/refunds"),
    pageSize: 50,
    formatError: formatActionError,
  });

  const [modalRefund, setModalRefund] = useState<RefundRequest | null>(null);
  const [modalDecision, setModalDecision] = useState<Decision>("approve");
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const handleCreateRefund = async (form: {
    work_order_id: string;
    amount: string;
    reason: string;
    refund_class: RefundClass;
    approver: string;
  }) => {
    setActionPending("create");
    setActionError(null);
    try {
      // 遷移至 spec-aligned tenant-scoped 三維 SoD 端點（ADR-0040v2 / FR-0014）。
      // tier 不傳——伺服器從 amount 推算；reason_code / requested_by_role 已不需要。
      const session = getCurrentSession();
      const tenantId = session?.tenantId;
      if (!tenantId) {
        throw new ApiError(400, {
          error_code: "NO_TENANT",
          message: "缺少 tenant，請重新登入",
        });
      }
      const res = await api.post<{ data: SoDRefundResult }>(
        `/tenants/${encodeURIComponent(tenantId)}/refunds`,
        {
          work_order_id: form.work_order_id,
          amount: Number(form.amount),
          refund_class: form.refund_class,
          reason: form.reason,
        },
        {
          headers: {
            // X-Initiator 須為合法 UUID（session.userId = JWT sub）
            "X-Initiator": session?.userId ?? "operator",
            // X-Approver 必填，且須與發起人不同（SoD），後端最終把關
            "X-Approver": form.approver,
          },
        },
      );
      const tier = res.data?.tier ?? "—";
      setActionToast(`退款申請已建立（tier ${tier}）`);
      setCreateModalOpen(false);
      // 重新 fetch 取最新（usePaginatedFetch 走 v2 tenantPath('/refunds')）
      await fetchRefunds();
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const decisionLabel = useMemo<Record<Decision, string>>(
    () => ({
      approve: t("decision.approve"),
      reject: t("decision.reject"),
      escalate: t("decision.escalate"),
    }),
    [t],
  );

  useEffect(() => {
    if (!actionToast) return;
    const t = setTimeout(() => setActionToast(null), 2400);
    return () => clearTimeout(t);
  }, [actionToast]);

  const handleOpenDecision = (refund: RefundRequest, decision: Decision) => {
    setModalRefund(refund);
    setModalDecision(decision);
    setActionError(null);
  };

  const handleSubmitDecision = async (reason: string) => {
    if (!modalRefund) return;
    const body: RefundDecisionBody = {
      decision: modalDecision,
      reason,
      dual_sign_required: modalRefund.requires_dual_sign ?? undefined,
    };
    setActionPending(modalRefund.id);
    setActionError(null);
    try {
      // api.post 第二參數本身即 request body;直傳 body,勿多包一層 { body }
      // （多包會送出 {"body":{...}} → 後端 decision/reason 頂層欄位缺失 422）
      const res = await api.post<RefundRequestEnvelope>(
        tenantPath(`/refunds/${modalRefund.id}/decision`),
        body,
      );
      const updated = res.data;
      if (updated) {
        // optimistic local update via hook mutate (per Phase 3.3 backlog §C2)
        mutate((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      }
      setActionToast(t("decision.submitted", { label: decisionLabel[modalDecision] }));
      setModalRefund(null);
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const slaCounts = useMemo(() => {
    const now = Date.now();
    let tier2 = 0;
    let tier8 = 0;
    let tierLong = 0;
    for (const r of items) {
      if (!isOpenForReview(r.status)) continue;
      const ageMs = now - new Date(r.created_at).getTime();
      if (ageMs <= SLA_TIER_2H_MS) tier2 += 1;
      else if (ageMs <= SLA_TIER_8H_MS) tier8 += 1;
      else tierLong += 1;
    }
    return { tier2, tier8, tierLong };
  }, [items]);

  const slaCards = [
    {
      label: t("sla.tier2"),
      count: slaCounts.tier2,
      labelColor: "#991B1B",
      countColor: "#DC2626",
      bgColor: "#FEE2E2",
    },
    {
      label: t("sla.tier8"),
      count: slaCounts.tier8,
      labelColor: "#92400E",
      countColor: "#D97706",
      bgColor: "#FEF3C7",
    },
    {
      label: t("sla.tierLong"),
      count: slaCounts.tierLong,
      labelColor: "#065F46",
      countColor: "#059669",
      bgColor: "#D1FAE5",
    },
  ];

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* flex-1 + space-y-5（非 flex flex-col gap-5）：避免子層被 flex-shrink 壓縮、
            內容超高時自然溢出觸發捲動。同 /admin/customers 捲軸失效修法。*/}
        <div className="flex-1 space-y-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <button
              onClick={() => fetchRefunds()}
              disabled={loading}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title={tc("refresh")}
            >
              <RefreshCw
                className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
              />
            </button>
            <button
              onClick={() => {
                setActionError(null);
                setCreateModalOpen(true);
              }}
              disabled={actionPending !== null}
              className="inline-flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-[6px] text-[13px] font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              title="建立退款申請"
            >
              <Plus className="h-4 w-4" />
              建立退款申請
            </button>
            <span
              className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
              style={{
                backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                color: error ? "#B91C1C" : "#15803D",
              }}
            >
              <span
                className="h-[6px] w-[6px] rounded-full"
                style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
              />
              {error ? tc("disconnected") : tc("connected")}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {updatedAt
                ? tc("lastUpdated", { time: updatedAt.toLocaleTimeString("zh-TW", { hour12: false }) })
                : "—"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">·</span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {hasMore
                ? tc("totalCountMore", { count: items.length })
                : tc("totalCount", { count: items.length })}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {actionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {actionError}
            </div>
          )}

          <div className="flex gap-3">
            {slaCards.map((card) => (
              <div
                key={card.label}
                className="flex flex-1 flex-col gap-1 rounded-lg px-4 py-3"
                style={{ backgroundColor: card.bgColor }}
              >
                <span
                  className="text-[13px] font-medium"
                  style={{ color: card.labelColor }}
                >
                  {card.label}
                </span>
                <span
                  className="text-[28px] font-bold"
                  style={{ color: card.countColor }}
                >
                  {card.count}
                </span>
              </div>
            ))}
          </div>

          <RefundReviewTable
            items={items}
            loading={loading}
            onDecide={handleOpenDecision}
            pendingId={actionPending}
          />

          {hasMore && (
            <div className="flex justify-center">
              <button
                onClick={loadMore}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? tc("loading") : tc("loadMore")}
              </button>
            </div>
          )}
        </div>
      </div>

      {modalRefund && (
        <DecisionModal
          refund={modalRefund}
          decision={modalDecision}
          onChangeDecision={setModalDecision}
          onClose={() => setModalRefund(null)}
          onSubmit={handleSubmitDecision}
          submitting={actionPending === modalRefund.id}
        />
      )}

      {createModalOpen && (
        <CreateRefundModal
          onCancel={() => setCreateModalOpen(false)}
          onSubmit={handleCreateRefund}
          submitting={actionPending === "create"}
          error={actionError}
        />
      )}

      {actionToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-lg">
          {actionToast}
        </div>
      )}
    </div>
  );
}

interface DecisionModalProps {
  refund: RefundRequest;
  decision: Decision;
  onChangeDecision: (d: Decision) => void;
  onClose: () => void;
  onSubmit: (reason: string) => void;
  submitting: boolean;
}

function DecisionModal({
  refund,
  decision,
  onChangeDecision,
  onClose,
  onSubmit,
  submitting,
}: DecisionModalProps) {
  const t = useTranslations("admin.refunds");
  const tc = useTranslations("admin.common");
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 500;
  const decisionStyle = useMemo<
    Record<Decision, { btn: string; label: string; hint: string }>
  >(
    () => ({
      approve: {
        btn: "bg-[var(--primary)] hover:opacity-90",
        label: t("decision.approve"),
        hint: t("modal.approveHint"),
      },
      reject: {
        btn: "bg-[#EF4444] hover:opacity-90",
        label: t("decision.reject"),
        hint: t("modal.rejectHint"),
      },
      escalate: {
        btn: "bg-[#3B82F6] hover:opacity-90",
        label: t("decision.escalate"),
        hint: t("modal.escalateHint"),
      },
    }),
    [t],
  );
  const cfg = decisionStyle[decision];
  const amountStr = (() => {
    const n = Number(refund.amount);
    return Number.isFinite(n)
      ? `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
      : `NT$ ${refund.amount}`;
  })();

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[520px] rounded-xl bg-[var(--bg-surface)] p-5 shadow-xl"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {t("modal.title")}
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-3 rounded-lg bg-[var(--bg-page)] px-3 py-2 text-[12px] text-[var(--text-secondary)]">
          <div>
            {t("modal.refundId")}
            <span className="font-mono text-[var(--text-primary)]">
              {refund.id.slice(0, 8)}
            </span>
          </div>
          <div>
            {t("modal.amount")}
            <span className="font-semibold text-[var(--text-primary)]">{amountStr}</span>
          </div>
          <div className="line-clamp-2">{t("modal.originalReason", { reason: refund.reason })}</div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {(["approve", "reject", "escalate"] as Decision[]).map((d) => {
            const active = d === decision;
            const tone = decisionStyle[d];
            return (
              <button
                key={d}
                onClick={() => onChangeDecision(d)}
                className={`rounded-lg border px-3 py-2 text-[13px] font-medium transition ${
                  active
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                }`}
              >
                {tone.label}
              </button>
            );
          })}
        </div>

        <p className="mt-2 text-[12px] leading-relaxed text-[var(--text-secondary)]">
          {cfg.hint}
        </p>

        <label className="mt-4 block text-[12px] font-medium text-[var(--text-secondary)]">
          {t("modal.reasonLabel")}
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value.slice(0, 500))}
          placeholder={t("modal.reasonPlaceholder")}
          className="mt-1 h-24 w-full resize-none rounded-md border border-[var(--border)] bg-white p-2 text-sm focus:border-[var(--primary)] focus:outline-none"
        />
        <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span>{t("modal.charCount", { count: trimmed.length })}</span>
          {refund.requires_dual_sign && (
            <span className="text-[#B45309]">
              {t("modal.dualSignNote")}
            </span>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-[var(--border)] px-3 py-[7px] text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          >
            {tc("cancel")}
          </button>
          <button
            disabled={!valid || submitting}
            onClick={() => onSubmit(trimmed)}
            className={`rounded-md px-4 py-[7px] text-[12px] font-medium text-white transition ${cfg.btn} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {submitting ? tc("submitting") : cfg.label}
          </button>
        </div>
      </div>
    </div>
  );
}


interface CreateRefundModalProps {
  onCancel: () => void;
  onSubmit: (form: {
    work_order_id: string;
    amount: string;
    reason: string;
    refund_class: RefundClass;
    approver: string;
  }) => Promise<void>;
  submitting: boolean;
  error: string | null;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function CreateRefundModal({
  onCancel,
  onSubmit,
  submitting,
  error,
}: CreateRefundModalProps) {
  const [workOrderId, setWorkOrderId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [refundClass, setRefundClass] = useState<RefundClass>("product");
  const [approver, setApprover] = useState("");

  // 覆核主管下拉：拉真實後台員工清單，排除發起人自己（SoD）+ 只列啟用帳號，
  // 取代原本手貼主管 UUID。
  const currentUserId = getCurrentSession()?.userId ?? "";
  const [staffList, setStaffList] = useState<StaffOption[]>([]);
  const [staffLoading, setStaffLoading] = useState(true);
  const [staffError, setStaffError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setStaffLoading(true);
      try {
        const res = await api.get<{
          items: { id: string; name: string; role: string; is_active: boolean }[];
        }>("/api/v1/staff");
        if (cancelled) return;
        const opts = (res.items ?? [])
          .filter((s) => s.id !== currentUserId && s.is_active)
          .map((s) => ({ id: s.id, name: s.name, role: s.role }));
        setStaffList(opts);
      } catch (e) {
        if (!cancelled) setStaffError(formatActionError(e));
      } finally {
        if (!cancelled) setStaffLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [currentUserId]);

  const valid =
    UUID_RE.test(workOrderId.trim()) &&
    /^\d+(\.\d{1,2})?$/.test(amount.trim()) &&
    Number(amount.trim()) > 0 &&
    reason.trim().length > 0 &&
    UUID_RE.test(approver.trim());

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            建立退款申請
          </span>
          <button
            onClick={onCancel}
            disabled={submitting}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              工單（搜尋公單號或客戶名，免手貼 UUID）
            </span>
            <WorkOrderPicker value={workOrderId} onChange={setWorkOrderId} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              退款金額（NT$）
            </span>
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={submitting}
              placeholder="例如 1500.00"
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              退款類別
            </span>
            <select
              value={refundClass}
              onChange={(e) => setRefundClass(e.target.value as RefundClass)}
              disabled={submitting}
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            >
              {REFUND_CLASSES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              退款原因敘述
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={submitting}
              rows={3}
              maxLength={500}
              placeholder="例如：商品到貨後 3 天即故障，客戶要求全額退款"
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              覆核主管（須與發起人不同，SoD）
            </span>
            <select
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              disabled={submitting || staffLoading}
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none disabled:opacity-60"
            >
              <option value="">
                {staffLoading
                  ? "載入員工清單中…"
                  : staffList.length === 0
                    ? "無可選的覆核主管"
                    : "請選擇覆核主管"}
              </option>
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}（{STAFF_ROLE_LABEL[s.role] ?? s.role}）
                </option>
              ))}
            </select>
            {staffError && (
              <span className="text-[11px] text-red-600">{staffError}</span>
            )}
          </label>
        </div>

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={submitting}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            disabled={!valid || submitting}
            onClick={() =>
              onSubmit({
                work_order_id: workOrderId.trim(),
                amount: amount.trim(),
                reason: reason.trim(),
                refund_class: refundClass,
                approver: approver.trim(),
              })
            }
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "建立中…" : "建立"}
          </button>
        </div>
      </div>
    </div>
  );
}
