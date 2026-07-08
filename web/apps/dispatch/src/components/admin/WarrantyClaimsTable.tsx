"use client";

import { useMemo } from "react";
import Link from "next/link";
import type { components } from "@shared/types/api.generated";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

type WarrantyClaim = components["schemas"]["WarrantyClaim"];
type WarrantyClaimStatus = components["schemas"]["WarrantyClaimStatus"];

interface Props {
  items: WarrantyClaim[];
  loading?: boolean;
  onDecide?: (claim: WarrantyClaim) => void;
  pendingId?: string | null;
}

const STATUS_TONE: Record<WarrantyClaimStatus, { textColor: string; bgColor: string }> = {
  filed: { textColor: "#92400E", bgColor: "#FEF3C7" },
  in_progress: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
  approved: { textColor: "#065F46", bgColor: "#D1FAE5" },
  rejected: { textColor: "#991B1B", bgColor: "#FEE2E2" },
  closed: { textColor: "#374151", bgColor: "#E5E7EB" },
};

const STATUS_KEY: Record<WarrantyClaimStatus, string> = {
  filed: "status.filed",
  in_progress: "status.inProgress",
  approved: "status.approved",
  rejected: "status.rejected",
  closed: "status.closed",
};

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00").getTime();
  const today = new Date(new Date().toISOString().slice(0, 10) + "T00:00:00").getTime();
  return Math.round((target - today) / ONE_DAY_MS);
}

function formatTwd(amount: string | null | undefined): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function WarrantyClaimsTable({
  items,
  loading,
  onDecide,
  pendingId,
}: Props) {
  const t = useTranslations("components.admin.warrantyClaims");

  const columns = useMemo(
    () => [
      { key: "id", label: t("cols.id"), width: "w-[110px] shrink-0" },
      { key: "device", label: t("cols.device"), width: "w-[150px] shrink-0" },
      { key: "warrantyStart", label: t("cols.warrantyStart"), width: "w-[100px] shrink-0" },
      { key: "warrantyEnd", label: t("cols.warrantyEnd"), width: "w-[100px] shrink-0" },
      { key: "remainingDays", label: t("cols.remainingDays"), width: "w-[90px] shrink-0" },
      { key: "warrantyPeriod", label: t("cols.warrantyPeriod"), width: "w-[80px] shrink-0" },
      { key: "claimStatus", label: t("cols.claimStatus"), width: "w-[90px] shrink-0" },
      { key: "discount", label: t("cols.discount"), width: "w-[100px] shrink-0" },
      { key: "actions", label: t("cols.actions"), width: "flex-1 min-w-0" },
    ],
    [t],
  );

  function remainingDisplay(remaining: number): { label: string; color: string; bold: boolean } {
    if (remaining < 0) {
      return {
        label: t("remaining.overdue", { days: Math.abs(remaining) }),
        color: "#DC2626",
        bold: true,
      };
    }
    if (remaining === 0) {
      return { label: t("remaining.today"), color: "#DC2626", bold: true };
    }
    if (remaining <= 30) {
      return { label: t("remaining.days", { days: remaining }), color: "#D97706", bold: true };
    }
    if (remaining <= 90) {
      return { label: t("remaining.days", { days: remaining }), color: "#D97706", bold: false };
    }
    return { label: t("remaining.days", { days: remaining }), color: "#059669", bold: false };
  }

  function periodBadge(isWithin: boolean, remaining: number): { label: string; textColor: string; bgColor: string } {
    if (!isWithin) return { label: t("period.expired"), textColor: "#B91C1C", bgColor: "#FEE2E2" };
    if (remaining <= 30) return { label: t("period.grace"), textColor: "#92400E", bgColor: "#FEF3C7" };
    return { label: t("period.active"), textColor: "#15803D", bgColor: "#DCFCE7" };
  }

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[#F8FAFC] border-b border-[var(--border)]">
        {columns.map((col) => (
          <div key={col.key} className={`flex items-center px-3 ${col.width}`}>
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
        const remaining = daysUntil(row.warranty_end_date);
        const remainingUi = remainingDisplay(remaining);
        const period = periodBadge(row.is_within_warranty, remaining);
        const tone = STATUS_TONE[row.status];

        return (
          <div
            key={row.id}
            className={`flex h-[56px] items-center bg-[var(--bg-surface)] ${
              idx < items.length - 1 ? "border-b border-[var(--border)]" : ""
            }`}
          >
            <div className="flex w-[110px] shrink-0 items-center px-3">
              <span
                className="font-mono text-xs font-medium text-[var(--text-primary)]"
                title={row.id}
              >
                {row.document_number ?? row.id.slice(0, 8)}
              </span>
            </div>

            <div className="flex w-[150px] shrink-0 flex-col justify-center px-3">
              <span className="truncate text-xs font-semibold text-[var(--text-primary)]">
                {row.device_brand}
              </span>
              <span className="truncate text-[11px] text-[var(--text-secondary)]">
                {row.device_model}
              </span>
            </div>

            <div className="flex w-[100px] shrink-0 items-center px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {row.warranty_start_date}
              </span>
            </div>

            <div className="flex w-[100px] shrink-0 items-center px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {row.warranty_end_date}
              </span>
            </div>

            <div className="flex w-[90px] shrink-0 items-center px-3">
              <span
                className="text-xs"
                style={{ color: remainingUi.color, fontWeight: remainingUi.bold ? 700 : 600 }}
              >
                {remainingUi.label}
              </span>
            </div>

            <div className="flex w-[80px] shrink-0 items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: period.textColor, backgroundColor: period.bgColor }}
              >
                {period.label}
              </span>
            </div>

            <div className="flex w-[90px] shrink-0 items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
              >
                {t(STATUS_KEY[row.status])}
              </span>
            </div>

            <div className="flex w-[100px] shrink-0 items-center px-3">
              <span className="font-mono text-[12px] text-[var(--text-primary)]">
                {formatTwd(row.discount_offered)}
              </span>
            </div>

            <div className="flex min-w-0 flex-1 items-center justify-end gap-[6px] px-3">
              <Link
                href={`/admin/warranty-claims/${row.id}`}
                className="rounded-md border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                {t("actions.viewDetails")}
              </Link>
              {(row.status === "filed" || row.status === "in_progress") && onDecide ? (
                <button
                  onClick={() => onDecide(row)}
                  disabled={pendingId !== null && pendingId !== undefined}
                  className="rounded-md bg-[var(--primary)] px-2 py-1 text-[11px] font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pendingId === row.id ? t("actions.reviewing") : t("actions.review")}
                </button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
