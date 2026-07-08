"use client";

import { useMemo } from "react";
import Link from "next/link";
import type { components } from "@shared/types/api.generated";
import { formatRelative } from "@shared/lib/format";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

type RefundRequest = components["schemas"]["RefundRequest"];
type RefundRequestStatus = components["schemas"]["RefundRequestStatus"];
type Decision = "approve" | "reject" | "escalate";

interface Props {
  items: RefundRequest[];
  loading?: boolean;
  onDecide?: (refund: RefundRequest, decision: Decision) => void;
  pendingId?: string | null;
}

// Tone (color) — separate from i18n label, same convention as other tables.
const STATUS_TONE: Record<RefundRequestStatus, { textColor: string; bgColor: string }> = {
  pending: { textColor: "#92400E", bgColor: "#FEF3C7" },
  csm_approved: { textColor: "#7C2D12", bgColor: "#FED7AA" },
  approved: { textColor: "#065F46", bgColor: "#D1FAE5" },
  rejected: { textColor: "#991B1B", bgColor: "#FEE2E2" },
  escalated: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
  executed: { textColor: "#374151", bgColor: "#E5E7EB" },
  cancelled: { textColor: "#374151", bgColor: "#E5E7EB" },
};

function formatTwd(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function isUrgentStatus(status: RefundRequestStatus): boolean {
  return (
    status === "escalated" ||
    status === "pending" ||
    status === "csm_approved"
  );
}

export default function RefundReviewTable({ items, loading, onDecide, pendingId }: Props) {
  const t = useTranslations("components.admin.refundReview");

  const columns = useMemo(
    () => [
      { key: "id", label: t("cols.id"), width: "w-[120px] shrink-0" },
      { key: "workOrder", label: t("cols.workOrder"), width: "w-[120px] shrink-0" },
      { key: "amount", label: t("cols.amount"), width: "w-[120px] shrink-0" },
      { key: "reason", label: t("cols.reason"), width: "flex-[2]" },
      { key: "dualSign", label: t("cols.dualSign"), width: "w-[60px] shrink-0" },
      { key: "approvalProgress", label: t("cols.approvalProgress"), width: "w-[100px] shrink-0" },
      { key: "status", label: t("cols.status"), width: "w-[110px] shrink-0" },
      { key: "createdAt", label: t("cols.createdAt"), width: "w-[150px] shrink-0" },
      { key: "actions", label: t("cols.actions"), width: "w-[160px] shrink-0" },
    ],
    [t],
  );

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center rounded-t-lg bg-[#F1F5F9]">
        {columns.map((col) => (
          <div
            key={col.key}
            className={`flex items-center px-[10px] ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
          {t("loading")}
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
          {t("empty")}
        </div>
      )}

      {items.map((row) => {
        const tone = STATUS_TONE[row.status];
        const urgent = isUrgentStatus(row.status);
        const chainLength = Array.isArray(row.approval_chain) ? row.approval_chain.length : 0;
        const isClosed = row.status === "executed" || row.status === "cancelled" || row.status === "rejected";

        const statusKeyMap: Record<RefundRequestStatus, string> = {
          pending: "status.pending",
          csm_approved: "status.csmApproved",
          approved: "status.approved",
          rejected: "status.rejected",
          escalated: "status.escalated",
          executed: "status.executed",
          cancelled: "status.cancelled",
        };

        return (
          <div
            key={row.id}
            className={`flex h-[56px] items-center border-b border-[var(--border)] last:border-b-0 ${
              urgent ? "bg-[#FEF2F2]" : ""
            }`}
          >
            <div className="flex w-[120px] shrink-0 items-center px-[10px]">
              <span
                className="font-mono text-xs text-[var(--text-primary)]"
                title={row.id}
              >
                {row.document_number ?? row.id.slice(0, 8)}
              </span>
            </div>

            <div className="flex w-[120px] shrink-0 items-center px-[10px]">
              <Link
                href={`/work-orders/${row.work_order_id}`}
                className="font-mono text-xs text-[var(--primary)] hover:underline"
              >
                {row.work_order_id.slice(0, 8)}
              </Link>
            </div>

            <div className="flex w-[120px] shrink-0 items-center px-[10px]">
              <span className="font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                {formatTwd(row.amount)}
              </span>
            </div>

            <div className="flex flex-[2] items-center px-[10px]">
              <span className="line-clamp-1 text-xs text-[var(--text-primary)]" title={row.reason}>
                {row.reason}
              </span>
            </div>

            <div className="flex w-[60px] shrink-0 items-center justify-center px-[6px]">
              {row.requires_dual_sign ? (
                <span className="rounded bg-[#FEE2E2] px-2 py-[2px] text-[10px] font-medium text-[#991B1B]">
                  {t("dualSign.required")}
                </span>
              ) : (
                <span className="text-[11px] text-[var(--text-secondary)]">—</span>
              )}
            </div>

            <div className="flex w-[100px] shrink-0 items-center justify-center px-[6px]">
              <span className="text-xs text-[var(--text-secondary)]">
                {chainLength === 0
                  ? t("chain.notStarted")
                  : t("chain.stepCount", { count: chainLength })}
              </span>
            </div>

            <div className="flex w-[110px] shrink-0 items-center justify-center px-[6px]">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
              >
                {t(statusKeyMap[row.status])}
              </span>
            </div>

            <div className="flex w-[150px] shrink-0 items-center px-[10px]">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {row.created_at ? formatRelative(row.created_at) : "—"}
              </span>
            </div>

            <div className="flex w-[160px] shrink-0 items-center justify-center gap-[6px] px-[6px]">
              {isClosed || row.status === "approved" ? (
                <span className="rounded-md bg-[#E2E8F0] px-3 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                  {row.status === "executed"
                    ? t("actions.executed")
                    : row.status === "approved"
                      ? t("actions.approved")
                      : row.status === "rejected"
                        ? t("actions.rejected")
                        : t("actions.cancelled")}
                </span>
              ) : row.status === "pending" || row.status === "csm_approved" ? (
                <>
                  <button
                    onClick={() => onDecide?.(row, "approve")}
                    disabled={!onDecide || pendingId === row.id}
                    className="rounded-md bg-[var(--primary)] px-3 py-1 text-[11px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    title={
                      row.status === "csm_approved"
                        ? t("actions.approveTitleSecondSign")
                        : row.requires_dual_sign
                          ? t("actions.approveTitleFirstWithDual")
                          : t("actions.approveTitleSimple")
                    }
                  >
                    {row.status === "csm_approved" ? t("actions.secondSign") : t("actions.approve")}
                  </button>
                  <button
                    onClick={() => onDecide?.(row, "reject")}
                    disabled={!onDecide || pendingId === row.id}
                    className="rounded-md bg-[#EF4444] px-3 py-1 text-[11px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("actions.reject")}
                  </button>
                </>
              ) : (
                <span className="rounded-md bg-[#DBEAFE] px-3 py-1 text-[11px] font-medium text-[#1E40AF]">
                  {t("actions.escalated")}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
