"use client";

import { useMemo } from "react";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";

type Reconciliation = components["schemas"]["Reconciliation"];
type ReconciliationStatus = components["schemas"]["ReconciliationStatus"];

interface Props {
  items: Reconciliation[];
  loading?: boolean;
  onApprove?: (recon: Reconciliation) => void;
  pendingApproveId?: string | null;
}

const STATUS_TONE: Record<
  ReconciliationStatus,
  { textColor: string; bgColor: string }
> = {
  pending: { textColor: "#92400E", bgColor: "#FEF3C7" },
  approved: { textColor: "#065F46", bgColor: "#D1FAE5" },
  disputed: { textColor: "#991B1B", bgColor: "#FEE2E2" },
};

function formatTwd(amount: string | null | undefined): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

function formatPeriod(start: string, end: string): string {
  return `${start.slice(0, 10)} ～ ${end.slice(0, 10)}`;
}

export default function ReconciliationsTable({
  items,
  loading,
  onApprove,
  pendingApproveId,
}: Props) {
  const t = useTranslations("components.accounting.reconciliationsTable");

  const columns = useMemo(
    () => [
      { label: t("cols.id"), width: "w-[100px] shrink-0" },
      { label: t("cols.technician"), width: "w-[140px] shrink-0" },
      { label: t("cols.period"), width: "w-[200px] shrink-0" },
      { label: t("cols.orders"), width: "w-[80px] shrink-0", align: "text-right" as const },
      { label: t("cols.revenue"), width: "w-[110px] shrink-0", align: "text-right" as const },
      { label: t("cols.platformFee"), width: "w-[110px] shrink-0", align: "text-right" as const },
      { label: t("cols.payout"), width: "w-[120px] shrink-0", align: "text-right" as const },
      { label: t("cols.status"), width: "w-[90px] shrink-0" },
      { label: t("cols.actions"), width: "flex-1 min-w-0" },
    ],
    [t],
  );

  const statusLabels: Record<ReconciliationStatus, string> = useMemo(
    () => ({
      pending: t("status.pending"),
      approved: t("status.approved"),
      disputed: t("status.disputed"),
    }),
    [t],
  );

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[#F8FAFC] border-b border-[var(--border)]">
        {columns.map((col) => (
          <div
            key={col.label}
            className={`flex items-center px-3 ${col.width} ${col.align ?? "text-left"}`}
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

      {items.map((row, idx) => {
        const tone = STATUS_TONE[row.status];
        const canApprove = row.status === "pending" && !!onApprove;
        return (
          <div
            key={row.id}
            className={`flex h-[56px] items-center bg-[var(--bg-surface)] ${
              idx < items.length - 1 ? "border-b border-[var(--border)]" : ""
            }`}
          >
            <div className="flex w-[100px] shrink-0 items-center px-3">
              <span className="font-mono text-xs text-[var(--text-primary)]">
                {row.id.slice(0, 8)}
              </span>
            </div>
            <div className="flex w-[140px] shrink-0 items-center px-3">
              <span className="truncate text-xs font-medium text-[var(--text-primary)]">
                {row.technician_name ?? row.technician_id.slice(0, 8)}
              </span>
            </div>
            <div className="flex w-[200px] shrink-0 items-center px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {formatPeriod(row.period_start, row.period_end)}
              </span>
            </div>
            <div className="flex w-[80px] shrink-0 items-center justify-end px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {row.total_orders}
              </span>
            </div>
            <div className="flex w-[110px] shrink-0 items-center justify-end px-3">
              <span className="font-mono text-[12px] text-[var(--text-primary)]">
                {formatTwd(row.total_revenue)}
              </span>
            </div>
            <div className="flex w-[110px] shrink-0 items-center justify-end px-3">
              <span className="font-mono text-[12px] text-[var(--text-secondary)]">
                {formatTwd(row.platform_fee)}
              </span>
            </div>
            <div className="flex w-[120px] shrink-0 items-center justify-end px-3">
              <span className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">
                {formatTwd(row.technician_payout)}
              </span>
            </div>
            <div className="flex w-[90px] shrink-0 items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
              >
                {statusLabels[row.status]}
              </span>
            </div>
            <div className="flex min-w-0 flex-1 items-center justify-end gap-[6px] px-3">
              {canApprove ? (
                <button
                  onClick={() => onApprove!(row)}
                  disabled={pendingApproveId !== null && pendingApproveId !== undefined}
                  className="rounded-md bg-[var(--success)] px-2 py-1 text-[11px] font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pendingApproveId === row.id ? t("processing") : t("approve")}
                </button>
              ) : (
                <span className="text-[11px] text-[var(--text-secondary)]">—</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
