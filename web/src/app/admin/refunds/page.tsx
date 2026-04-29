"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import RefundReviewTable from "@/components/admin/RefundReviewTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type RefundRequest = components["schemas"]["RefundRequest"];
type RefundRequestPage = components["schemas"]["RefundRequestPage"];
type RefundRequestEnvelope = components["schemas"]["RefundRequestEnvelope"];
type RefundDecisionBody = components["schemas"]["RefundDecision"];
type Decision = "approve" | "reject" | "escalate";

const DECISION_LABEL: Record<Decision, string> = {
  approve: "核准退款",
  reject: "拒絕退款",
  escalate: "升級審批",
};

const SLA_TIER_2H_MS = 2 * 60 * 60 * 1000;
const SLA_TIER_8H_MS = 8 * 60 * 60 * 1000;

function isOpenForReview(status: RefundRequest["status"]): boolean {
  return status === "pending" || status === "escalated";
}

function formatActionError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

export default function RefundReviewPage() {
  const [items, setItems] = useState<RefundRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const [modalRefund, setModalRefund] = useState<RefundRequest | null>(null);
  const [modalDecision, setModalDecision] = useState<Decision>("approve");
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);

  const fetchRefunds = async (opts?: { append?: boolean; cursor?: string | null }) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      if (opts?.cursor) query.cursor = opts.cursor;
      const res = await api.get<RefundRequestPage>("/api/v1/refunds", { query });
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
    fetchRefunds();
  }, []);

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
      const res = await api.post<RefundRequestEnvelope>(
        `/api/v1/refunds/${modalRefund.id}/decision`,
        { body },
      );
      const updated = res.data;
      if (updated) {
        setItems((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      }
      setActionToast(`${DECISION_LABEL[modalDecision]}已送出`);
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
      label: "申請 ≤ 2 小時",
      count: slaCounts.tier2,
      labelColor: "#991B1B",
      countColor: "#DC2626",
      bgColor: "#FEE2E2",
    },
    {
      label: "申請 ≤ 8 小時",
      count: slaCounts.tier8,
      labelColor: "#92400E",
      countColor: "#D97706",
      bgColor: "#FEF3C7",
    },
    {
      label: "申請 > 8 小時",
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
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              退款審核佇列
            </h1>
            <button
              onClick={() => fetchRefunds()}
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

          <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
            列表為 listRefundRequests 即時資料；SLA 分群以「申請建立至今經過時間」估算（2h / 8h / &gt;8h）。
            核准 / 拒絕 / 升級已接 submitRefundDecision；雙簽流程於 MVP 簡化為單步推進，多步簽核流程待後續排入。
          </div>

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
                onClick={() => fetchRefunds({ append: true, cursor: nextCursor })}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
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
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 500;
  const decisionStyle: Record<
    Decision,
    { btn: string; label: string; hint: string }
  > = {
    approve: {
      btn: "bg-[var(--primary)] hover:opacity-90",
      label: "核准退款",
      hint: "確認核准後，狀態變更為「已核准」。後續仍需出納執行打款。",
    },
    reject: {
      btn: "bg-[#EF4444] hover:opacity-90",
      label: "拒絕退款",
      hint: "拒絕後申請結束，需在原因欄位寫明客戶可理解的拒絕理由。",
    },
    escalate: {
      btn: "bg-[#3B82F6] hover:opacity-90",
      label: "升級審批",
      hint: "金額或情境超出本人權限時使用，狀態變更為「已升級」。",
    },
  };
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
            退款審批決策
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
            退款編號：
            <span className="font-mono text-[var(--text-primary)]">
              {refund.id.slice(0, 8)}
            </span>
          </div>
          <div>
            金額：
            <span className="font-semibold text-[var(--text-primary)]">{amountStr}</span>
          </div>
          <div className="line-clamp-2">原始原因：{refund.reason}</div>
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
          審批原因（必填，最多 500 字）
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value.slice(0, 500))}
          placeholder="請說明本次決策的依據（將寫入 approval_chain）"
          className="mt-1 h-24 w-full resize-none rounded-md border border-[var(--border)] bg-white p-2 text-sm focus:border-[var(--primary)] focus:outline-none"
        />
        <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span>{trimmed.length} / 500</span>
          {refund.requires_dual_sign && (
            <span className="text-[#B45309]">
              本案標示需雙簽，MVP 將於單步寫入後保留稽核紀錄。
            </span>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-[var(--border)] px-3 py-[7px] text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          >
            取消
          </button>
          <button
            disabled={!valid || submitting}
            onClick={() => onSubmit(trimmed)}
            className={`rounded-md px-4 py-[7px] text-[12px] font-medium text-white transition ${cfg.btn} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {submitting ? "送出中…" : cfg.label}
          </button>
        </div>
      </div>
    </div>
  );
}
