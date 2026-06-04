"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Info, Plus, RefreshCw, Search, ShieldCheck, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WarrantyClaimsTable from "@/components/admin/WarrantyClaimsTable";
import { ApiError, api, getCurrentSession, tenantPath } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type WarrantyClaim = components["schemas"]["WarrantyClaim"];
type WarrantyClaimEnvelope = components["schemas"]["WarrantyClaimEnvelope"];
type WarrantyClaimStatus = components["schemas"]["WarrantyClaimStatus"];
type WarrantyDecision = components["schemas"]["WarrantyDecision"];
type DecisionValue = WarrantyDecision["decision"];

function formatWarrantyError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

interface StatusTab {
  value: WarrantyClaimStatus | "all";
}

const statusTabs: StatusTab[] = [
  { value: "all" },
  { value: "filed" },
  { value: "in_progress" },
  { value: "approved" },
  { value: "rejected" },
  { value: "closed" },
];

export default function WarrantyClaimsPage() {
  const t = useTranslations("admin.warranty");
  const tc = useTranslations("admin.common");
  const [activeTab, setActiveTab] = useState<StatusTab["value"]>("all");
  const [modalClaim, setModalClaim] = useState<WarrantyClaim | null>(null);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const {
    items,
    cursor: nextCursor,
    hasMore,
    lastFetchedAt: updatedAt,
    loading,
    error,
    loadMore,
    refresh: fetchClaims,
    mutate,
  } = usePaginatedFetch<WarrantyClaim>({
    // CR-0009 step-extend：warranty_claims_v2 補 listWarrantyClaimsV2 endpoint
    path: tenantPath("/warranty-claims"),
    pageSize: 50,
    query: activeTab !== "all" ? { status: activeTab } : undefined,
    queryKey: `tab=${activeTab}`,
    formatError: formatWarrantyError,
  });

  const handleCreateClaim = async (form: {
    customer_id: string;
    work_order_id: string;
    device_brand: string;
    device_model: string;
    claim_type: string;
    dispute_reason: string;
  }) => {
    setActionPending("create");
    setActionError(null);
    try {
      const session = getCurrentSession();
      const tenantId = session?.tenantId ?? "00000000-0000-0000-0000-000000000001";
      await api.post<WarrantyClaimEnvelope>(
        `/tenants/${encodeURIComponent(tenantId)}/warranty-claims`,
        {
          customer_id: form.customer_id,
          work_order_id: form.work_order_id || undefined,
          device_brand: form.device_brand,
          device_model: form.device_model,
          claim_type: form.claim_type,
          dispute_reason: form.dispute_reason || undefined,
          requested_by_role: "customer_service",
        },
      );
      setActionToast("保固申訴已建立");
      setCreateModalOpen(false);
      await fetchClaims();
    } catch (e) {
      setActionError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setActionPending(null);
    }
  };

  useEffect(() => {
    if (!actionToast) return;
    const t = setTimeout(() => setActionToast(null), 2400);
    return () => clearTimeout(t);
  }, [actionToast]);

  const handleSubmitDecision = async (
    decision: DecisionValue,
    resolution: string,
    discountOffered: string,
  ) => {
    if (!modalClaim) return;
    setActionPending(modalClaim.id);
    setActionError(null);
    try {
      const body: Record<string, unknown> = { decision };
      if (resolution) body.resolution = resolution;
      if (decision === "approve" && discountOffered) {
        body.discount_offered = discountOffered;
      }
      const res = await api.post<WarrantyClaimEnvelope>(
        // CR-0009 step-extend：warranty_claims_v2 補 submitWarrantyDecisionV2
        tenantPath(`/warranty-claims/${encodeURIComponent(modalClaim.id)}/decision`),
        body,
      );
      const updated = res.data ?? null;
      if (updated) {
        // optimistic local update via hook mutate (per Phase 3.3 backlog §C2)
        mutate((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      }
      setModalClaim(null);
      const tone =
        decision === "approve"
          ? t("toast.approved")
          : decision === "reject"
            ? t("toast.rejected")
            : t("toast.startReview");
      setActionToast(tone);
    } catch (e) {
      setActionError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setActionPending(null);
    }
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <button
              onClick={fetchClaims}
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
              title="建立保固申訴（F-015 dual-trigger CS 路徑）"
            >
              <Plus className="h-4 w-4" />
              建立保固申訴
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

          <div className="flex items-center gap-[10px] rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-4 py-3">
            <Info className="h-5 w-5 shrink-0 text-[#1D4ED8]" />
            <span className="text-[13px] leading-[1.5] text-[#1D4ED8]">
              {t("ruleNotice")}
            </span>
          </div>

          {actionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {tc("approvalFailed", { error: actionError })}
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="flex overflow-hidden rounded-lg border border-[var(--border)]">
              {statusTabs.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setActiveTab(tab.value)}
                  className={`px-4 py-2 text-[13px] font-medium ${
                    activeTab === tab.value
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--bg-surface)] text-[var(--text-secondary)]"
                  }`}
                >
                  {t(`tabs.${tab.value}`)}
                </button>
              ))}
            </div>

            <div
              className="flex w-[300px] cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 opacity-60"
              title={tc("comingSoon")}
            >
              <Search className="h-4 w-4 text-[var(--text-disabled)]" />
              <input
                disabled
                type="text"
                placeholder={t("searchPlaceholder")}
                className="flex-1 cursor-not-allowed bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>
          </div>

          <WarrantyClaimsTable
            items={items}
            loading={loading}
            onDecide={(claim) => {
              setActionError(null);
              setModalClaim(claim);
            }}
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

      {modalClaim && (
        <DecisionModal
          claim={modalClaim}
          pending={actionPending === modalClaim.id}
          onCancel={() => setModalClaim(null)}
          onSubmit={handleSubmitDecision}
        />
      )}

      {createModalOpen && (
        <CreateWarrantyModal
          onCancel={() => setCreateModalOpen(false)}
          onSubmit={handleCreateClaim}
          submitting={actionPending === "create"}
          error={actionError}
        />
      )}

      {actionToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {actionToast}
        </div>
      )}
    </div>
  );
}

const DECISION_OPTIONS_META: { value: DecisionValue; color: string; bg: string }[] = [
  { value: "approve", color: "#065F46", bg: "#D1FAE5" },
  { value: "reject", color: "#991B1B", bg: "#FEE2E2" },
  { value: "start_review", color: "#1E40AF", bg: "#DBEAFE" },
];

function DecisionModal({
  claim,
  pending,
  onCancel,
  onSubmit,
}: {
  claim: WarrantyClaim;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (
    decision: DecisionValue,
    resolution: string,
    discountOffered: string,
  ) => Promise<void>;
}) {
  const t = useTranslations("admin.warranty");
  const tc = useTranslations("admin.common");
  const [decision, setDecision] = useState<DecisionValue>("approve");
  const [resolution, setResolution] = useState("");
  const [discount, setDiscount] = useState("");
  const trimmed = resolution.trim();
  const decimalOk = discount === "" || /^-?\d+(\.\d{1,2})?$/.test(discount.trim());
  const requiresResolution = decision === "approve" || decision === "reject";
  const valid =
    (!requiresResolution || trimmed.length > 0) &&
    trimmed.length <= 500 &&
    decimalOk;

  const decisionOptions = useMemo(
    () =>
      DECISION_OPTIONS_META.map((meta) => ({
        ...meta,
        label:
          meta.value === "approve"
            ? t("decision.approve")
            : meta.value === "reject"
              ? t("decision.reject")
              : t("decision.startReview"),
        hint:
          meta.value === "approve"
            ? t("decision.approveHint")
            : meta.value === "reject"
              ? t("decision.rejectHint")
              : t("decision.startReviewHint"),
      })),
    [t],
  );

  const activeOpt = decisionOptions.find((o) => o.value === decision)!;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[560px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-1 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("modal.title")}
          </span>
        </div>
        <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[var(--text-secondary)]">
          <span className="font-mono text-[var(--text-primary)]">{claim.id.slice(0, 8)}</span>
          <span>·</span>
          <span>
            {claim.device_brand} {claim.device_model}
          </span>
          <span>·</span>
          <span>
            {t("modal.warrantyUntil")} <span className="text-[var(--text-primary)]">{claim.warranty_end_date}</span>
            {claim.is_within_warranty ? t("modal.withinWarranty") : t("modal.outOfWarranty")}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          {decisionOptions.map((opt) => {
            const active = opt.value === decision;
            return (
              <button
                key={opt.value}
                onClick={() => setDecision(opt.value)}
                className={`rounded-lg border px-3 py-3 text-left transition ${
                  active
                    ? "border-[var(--primary)] bg-[var(--primary-light)]"
                    : "border-[var(--border)] hover:bg-[var(--bg-page)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="rounded px-2 py-[2px] text-[11px] font-semibold"
                    style={{ color: opt.color, backgroundColor: opt.bg }}
                  >
                    {opt.label}
                  </span>
                  {active && (
                    <CheckCircle2 className="h-4 w-4 text-[var(--primary)]" />
                  )}
                </div>
                <div className="mt-1 text-[12px] leading-[1.5] text-[var(--text-secondary)]">
                  {opt.hint}
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            {t("modal.resolutionLabel")}
            {requiresResolution && <span className="text-[var(--error)]"> *</span>}
            <span className="ml-1 text-[var(--text-disabled)]">{t("modal.resolutionMaxHint")}</span>
          </label>
          <textarea
            value={resolution}
            onChange={(e) => setResolution(e.target.value.slice(0, 500))}
            rows={4}
            placeholder={
              decision === "approve"
                ? t("modal.resolutionPlaceholderApprove")
                : decision === "reject"
                  ? t("modal.resolutionPlaceholderReject")
                  : t("modal.resolutionPlaceholderReview")
            }
            className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
          />
          <span className="text-[11px] text-[var(--text-disabled)]">
            {trimmed.length} / 500
          </span>
        </div>

        {decision === "approve" && (
          <div className="mt-3 flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("modal.discountLabel")}
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
              placeholder={t("modal.discountPlaceholder")}
              className={`rounded-md border px-3 py-2 text-[13px] focus:outline-none ${
                decimalOk
                  ? "border-[var(--border)] focus:border-[var(--primary)]"
                  : "border-red-300 focus:border-red-400"
              }`}
            />
            {!decimalOk && (
              <span className="text-[11px] text-red-600">
                {t("modal.discountFormatError")}
              </span>
            )}
          </div>
        )}

        <p
          className="mt-3 rounded-md px-3 py-2 text-[12px] leading-[1.6]"
          style={{ color: activeOpt.color, backgroundColor: activeOpt.bg }}
        >
          {t("modal.decisionFinalHint", { label: activeOpt.label })}
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            <X className="mr-1 inline h-3 w-3" />
            {tc("back")}
          </button>
          <button
            onClick={() => onSubmit(decision, trimmed, discount.trim())}
            disabled={pending || !valid}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? tc("submitting") : tc("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface CreateWarrantyModalProps {
  onCancel: () => void;
  onSubmit: (form: {
    customer_id: string;
    work_order_id: string;
    device_brand: string;
    device_model: string;
    claim_type: string;
    dispute_reason: string;
  }) => Promise<void>;
  submitting: boolean;
  error: string | null;
}

const CLAIM_TYPES: { value: string; label: string }[] = [
  { value: "defective", label: "瑕疵" },
  { value: "malfunction", label: "故障" },
  { value: "premature_failure", label: "未到使用年限失效" },
  { value: "missing_parts", label: "缺件" },
  { value: "other", label: "其他" },
];

function CreateWarrantyModal({
  onCancel,
  onSubmit,
  submitting,
  error,
}: CreateWarrantyModalProps) {
  const [customerId, setCustomerId] = useState("");
  const [workOrderId, setWorkOrderId] = useState("");
  const [deviceBrand, setDeviceBrand] = useState("");
  const [deviceModel, setDeviceModel] = useState("");
  const [claimType, setClaimType] = useState("defective");
  const [disputeReason, setDisputeReason] = useState("");

  const valid =
    /^[0-9a-f-]{36}$/i.test(customerId.trim()) &&
    deviceBrand.trim().length > 0 &&
    deviceModel.trim().length > 0;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            建立保固申訴
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
              客戶 ID（UUID，必填）
            </span>
            <input
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              disabled={submitting}
              placeholder="00000000-0000-0000-0000-000000000000"
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-mono focus:border-[var(--primary)] focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              工單 ID（UUID，可選）
            </span>
            <input
              value={workOrderId}
              onChange={(e) => setWorkOrderId(e.target.value)}
              disabled={submitting}
              placeholder="（可留空）"
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-mono focus:border-[var(--primary)] focus:outline-none"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                品牌
              </span>
              <input
                value={deviceBrand}
                onChange={(e) => setDeviceBrand(e.target.value)}
                disabled={submitting}
                maxLength={100}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                型號
              </span>
              <input
                value={deviceModel}
                onChange={(e) => setDeviceModel(e.target.value)}
                disabled={submitting}
                maxLength={100}
                className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
              />
            </label>
          </div>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              申訴類型
            </span>
            <select
              value={claimType}
              onChange={(e) => setClaimType(e.target.value)}
              disabled={submitting}
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            >
              {CLAIM_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-[var(--text-secondary)]">
              申訴敘述（可選）
            </span>
            <textarea
              value={disputeReason}
              onChange={(e) => setDisputeReason(e.target.value)}
              disabled={submitting}
              rows={2}
              maxLength={500}
              className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
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
                customer_id: customerId.trim(),
                work_order_id: workOrderId.trim(),
                device_brand: deviceBrand.trim(),
                device_model: deviceModel.trim(),
                claim_type: claimType,
                dispute_reason: disputeReason.trim(),
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
