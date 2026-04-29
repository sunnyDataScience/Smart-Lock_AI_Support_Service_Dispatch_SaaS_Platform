"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Info, RefreshCw, Search, ShieldCheck, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WarrantyClaimsTable from "@/components/admin/WarrantyClaimsTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WarrantyClaim = components["schemas"]["WarrantyClaim"];
type WarrantyClaimEnvelope = components["schemas"]["WarrantyClaimEnvelope"];
type WarrantyClaimPage = components["schemas"]["WarrantyClaimPage"];
type WarrantyClaimStatus = components["schemas"]["WarrantyClaimStatus"];
type WarrantyDecision = components["schemas"]["WarrantyDecision"];
type DecisionValue = WarrantyDecision["decision"];

interface StatusTab {
  label: string;
  value: WarrantyClaimStatus | "all";
}

const statusTabs: StatusTab[] = [
  { label: "全部", value: "all" },
  { label: "已申請", value: "filed" },
  { label: "處理中", value: "in_progress" },
  { label: "已核准", value: "approved" },
  { label: "已拒絕", value: "rejected" },
  { label: "已結案", value: "closed" },
];

export default function WarrantyClaimsPage() {
  const [activeTab, setActiveTab] = useState<StatusTab["value"]>("all");
  const [items, setItems] = useState<WarrantyClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [modalClaim, setModalClaim] = useState<WarrantyClaim | null>(null);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);

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
        `/api/v1/warranty-claims/${encodeURIComponent(modalClaim.id)}/decision`,
        body,
      );
      const updated = res.data ?? null;
      if (updated) {
        setItems((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      }
      setModalClaim(null);
      const tone =
        decision === "approve"
          ? "已核准保固"
          : decision === "reject"
            ? "已拒絕保固"
            : "已轉入處理中";
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

  const fetchClaims = async (
    opts?: { append?: boolean; cursor?: string | null; status?: StatusTab["value"] },
  ) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      const status = opts?.status ?? activeTab;
      if (status !== "all") query.status = status;
      if (opts?.cursor) query.cursor = opts.cursor;
      const res = await api.get<WarrantyClaimPage>("/api/v1/warranty-claims", { query });
      const newItems = res.items ?? [];
      setItems((prev) => (opts?.append ? [...prev, ...newItems] : newItems));
      setNextCursor(res.next_cursor ?? null);
      setHasMore(res.has_more ?? false);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaims({ status: activeTab });
  }, [activeTab]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              保固申請管理
            </h1>
            <button
              onClick={() => fetchClaims({ status: activeTab })}
              disabled={loading}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title="重新整理"
            >
              <RefreshCw
                className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
              />
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
              {error ? "連線失敗" : "已連線"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {updatedAt
                ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
                : "—"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">·</span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              共 {items.length}{hasMore ? "+" : ""} 筆
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
              保固起算日以「交屋日期」為準，非「入住日期」。此為系統核心規則，所有保固計算均依據此原則。
            </span>
          </div>

          <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
            列表為 listWarrantyClaims 即時資料；保固期狀態（有效 / 寬限期 / 已過期）由前端依
            warranty_end_date 與 is_within_warranty 即時計算。審批決策已上線（filed /
            in_progress 可下 approve / reject / start_review）；檢視詳情與證據縮圖待 warranty
            詳情頁與上傳路徑上線後接入。
          </div>

          {actionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              審批失敗：{actionError}
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
                  {tab.label}
                </button>
              ))}
            </div>

            <div
              className="flex w-[300px] cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 opacity-60"
              title="即將推出"
            >
              <Search className="h-4 w-4 text-[var(--text-disabled)]" />
              <input
                disabled
                type="text"
                placeholder="搜尋案件編號、設備或客戶..."
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
                onClick={() => fetchClaims({ append: true, cursor: nextCursor, status: activeTab })}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
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

      {actionToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {actionToast}
        </div>
      )}
    </div>
  );
}

const DECISION_OPTIONS: { value: DecisionValue; label: string; hint: string; color: string; bg: string }[] = [
  {
    value: "approve",
    label: "核准",
    hint: "保固有效或經審核同意：可附保固外折讓金額。",
    color: "#065F46",
    bg: "#D1FAE5",
  },
  {
    value: "reject",
    label: "拒絕",
    hint: "已過保固或不符合條件：必填拒絕原因供客戶查證。",
    color: "#991B1B",
    bg: "#FEE2E2",
  },
  {
    value: "start_review",
    label: "轉入處理中",
    hint: "需蒐證或聯繫客戶：暫推進到 in_progress，後續再下最終決策。",
    color: "#1E40AF",
    bg: "#DBEAFE",
  },
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

  const activeOpt = DECISION_OPTIONS.find((o) => o.value === decision)!;

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
            保固審批決策
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
            保固至 <span className="text-[var(--text-primary)]">{claim.warranty_end_date}</span>
            {claim.is_within_warranty ? "（保固內）" : "（已過保）"}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          {DECISION_OPTIONS.map((opt) => {
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
            審批意見 / 處理結果
            {requiresResolution && <span className="text-[var(--error)]"> *</span>}
            <span className="ml-1 text-[var(--text-disabled)]">（最多 500 字）</span>
          </label>
          <textarea
            value={resolution}
            onChange={(e) => setResolution(e.target.value.slice(0, 500))}
            rows={4}
            placeholder={
              decision === "approve"
                ? "例如：保固期內主板異常，核准免費更換"
                : decision === "reject"
                  ? "例如：已過保固期 18 個月，且設備外觀有人為損傷痕跡"
                  : "例如：客戶補件中，待提供購買發票後再覆審"
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
              折讓金額 / 折扣（NT$，可留空）
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
              placeholder="例如：1500.00 或 0 表示完全免費"
              className={`rounded-md border px-3 py-2 text-[13px] focus:outline-none ${
                decimalOk
                  ? "border-[var(--border)] focus:border-[var(--primary)]"
                  : "border-red-300 focus:border-red-400"
              }`}
            />
            {!decimalOk && (
              <span className="text-[11px] text-red-600">
                金額格式應為小數兩位內的數字
              </span>
            )}
          </div>
        )}

        <p
          className="mt-3 rounded-md px-3 py-2 text-[12px] leading-[1.6]"
          style={{ color: activeOpt.color, backgroundColor: activeOpt.bg }}
        >
          送出後狀態將推進到「{activeOpt.label}」；approve / reject 為終局，無法再變更。
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            <X className="mr-1 inline h-3 w-3" />
            返回
          </button>
          <button
            onClick={() => onSubmit(decision, trimmed, discount.trim())}
            disabled={pending || !valid}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認送出"}
          </button>
        </div>
      </div>
    </div>
  );
}
