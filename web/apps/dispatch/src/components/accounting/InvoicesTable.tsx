"use client";

import { useMemo } from "react";
import Link from "next/link";
import { Eye } from "lucide-react";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";
import { formatRelative } from "@shared/lib/format";

type Invoice = components["schemas"]["Invoice"];
type InvoiceStatus = components["schemas"]["InvoiceStatus"];

interface Props {
  items: Invoice[];
  loading?: boolean;
}

const STATUS_TONE: Record<InvoiceStatus, { textColor: string; bgColor: string }> = {
  pending: { textColor: "#92400E", bgColor: "#FEF3C7" },
  issued: { textColor: "#065F46", bgColor: "#D1FAE5" },
  allowance_pending: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
  voided: { textColor: "#991B1B", bgColor: "#FEE2E2" },
  reopened: { textColor: "#5B21B6", bgColor: "#EDE9FE" },
};

function formatTwd(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function InvoicesTable({ items, loading }: Props) {
  const t = useTranslations("components.accounting.invoicesTable");

  const columns = useMemo(
    () => [
      { label: t("cols.invoiceNumber"), width: "w-[140px] shrink-0" },
      { label: t("cols.workOrder"), width: "w-[120px] shrink-0" },
      { label: t("cols.amount"), width: "w-[140px] shrink-0" },
      { label: t("cols.category"), width: "w-[110px] shrink-0" },
      { label: t("cols.status"), width: "w-[110px] shrink-0" },
      { label: t("cols.issuedAt"), width: "w-[160px] shrink-0" },
      { label: t("cols.updatedAt"), width: "w-[160px] shrink-0" },
      { label: t("cols.actions"), width: "flex-1 min-w-0" },
    ],
    [t],
  );

  const statusLabels: Record<InvoiceStatus, string> = useMemo(
    () => ({
      pending: t("status.pending"),
      issued: t("status.issued"),
      allowance_pending: t("status.allowance_pending"),
      voided: t("status.voided"),
      reopened: t("status.reopened"),
    }),
    [t],
  );

  const categoryLabel: Record<string, string> = useMemo(
    () => ({
      service_fee: t("category.service_fee"),
      travel_fee: t("category.travel_fee"),
      parts: t("category.parts"),
      other: t("category.other"),
    }),
    [t],
  );

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        {columns.map((col) => (
          <div key={col.label} className={`flex items-center px-2 ${col.width}`}>
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Loading / Empty */}
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

      {/* Data Rows */}
      {items.map((inv) => {
        const tone = STATUS_TONE[inv.status];
        const isVoided = inv.status === "voided";

        return (
          <div
            key={inv.id}
            className={`flex h-[52px] items-center border-b border-[var(--border)] px-8 ${
              isVoided ? "border-l-[3px] border-l-[#EF4444] bg-[#FEF2F2]" : ""
            }`}
          >
            {/* Invoice Number */}
            <div className="flex w-[140px] shrink-0 items-center px-2">
              <span className="font-['IBM_Plex_Mono'] text-[13px] font-medium text-[var(--text-primary)]">
                {inv.invoice_number}
              </span>
            </div>

            {/* Work Order */}
            <div className="flex w-[120px] shrink-0 items-center px-2">
              <Link
                href={`/work-orders/${inv.work_order_id}`}
                className="font-mono text-[13px] font-medium text-[var(--primary)] hover:underline"
              >
                {inv.work_order_id.slice(0, 8)}
              </Link>
            </div>

            {/* Amount */}
            <div className="flex w-[140px] shrink-0 items-center px-2">
              <span className="font-['IBM_Plex_Mono'] text-[13px] font-semibold text-[var(--text-primary)]">
                {formatTwd(inv.amount)}
              </span>
            </div>

            {/* Tax Category */}
            <div className="flex w-[110px] shrink-0 items-center px-2">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {inv.category ? categoryLabel[inv.category] ?? inv.category : "—"}
              </span>
            </div>

            {/* Status */}
            <div className="flex w-[110px] shrink-0 items-center px-2">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
              >
                {statusLabels[inv.status]}
              </span>
            </div>

            {/* Issued At */}
            <div className="flex w-[160px] shrink-0 items-center px-2">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {inv.issued_at ? formatRelative(inv.issued_at) : "—"}
              </span>
            </div>

            {/* Updated At */}
            <div className="flex w-[160px] shrink-0 items-center px-2">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {inv.updated_at ? formatRelative(inv.updated_at) : "—"}
              </span>
            </div>

            {/* Actions */}
            <div className="flex min-w-0 flex-1 items-center gap-1 px-2">
              <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
