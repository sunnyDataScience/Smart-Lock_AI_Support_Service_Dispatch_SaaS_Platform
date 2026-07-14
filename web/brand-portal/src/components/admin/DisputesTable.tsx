"use client";

import { useMemo } from "react";
import type { components } from "@/types/api.generated";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type Dispute = components["schemas"]["Dispute"];
type DisputeType = components["schemas"]["DisputeType"];
type DisputeStatus = components["schemas"]["DisputeStatus"];

interface Props {
  items: Dispute[];
  loading?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}

const TYPE_TONE: Record<DisputeType, { textColor: string; bgColor: string }> = {
  pricing: { textColor: "#2563EB", bgColor: "#DBEAFE" },
  quality: { textColor: "#7C3AED", bgColor: "#EDE9FE" },
  warranty: { textColor: "#059669", bgColor: "#D1FAE5" },
  cancellation_fee: { textColor: "#EA580C", bgColor: "#FFEDD5" },
  settlement: { textColor: "#DB2777", bgColor: "#FCE7F3" },
};

const TYPE_KEY: Record<DisputeType, string> = {
  pricing: "type.pricing",
  quality: "type.quality",
  warranty: "type.warranty",
  cancellation_fee: "type.cancellationFee",
  settlement: "type.settlement",
};

// 註：後端 dispute_v2_service._VALID_STATUS 另有 mediation/escalated/closed_withdrawn
// （openapi DisputeStatus enum 未同步，故 map 放寬為 string key；原本這三態直接漏原始碼）
const STATUS_TONE: Record<string, { textColor: string; bgColor: string }> = {
  filed: { textColor: "#D97706", bgColor: "#FEF3C7" },
  in_review: { textColor: "#2563EB", bgColor: "#DBEAFE" },
  mediation: { textColor: "#7C3AED", bgColor: "#EDE9FE" },
  escalated: { textColor: "#DC2626", bgColor: "#FEE2E2" },
  resolved: { textColor: "#059669", bgColor: "#D1FAE5" },
  rejected: { textColor: "#64748B", bgColor: "#F1F5F9" },
  closed: { textColor: "#374151", bgColor: "#E5E7EB" },
  closed_withdrawn: { textColor: "#374151", bgColor: "#E5E7EB" },
};

const STATUS_KEY: Record<string, string> = {
  filed: "status.filed",
  in_review: "status.inReview",
  mediation: "status.mediation",
  escalated: "status.escalated",
  resolved: "status.resolved",
  rejected: "status.rejected",
  closed: "status.closed",
  closed_withdrawn: "status.closedWithdrawn",
};

function formatTwd(amount: string | null | undefined): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

export default function DisputesTable({ items, loading, selectedId, onSelect }: Props) {
  const t = useTranslations("components.admin.disputes");

  const columns = useMemo(
    () => [
      { key: "id", label: t("cols.id"), width: "w-[140px] shrink-0" },
      { key: "type", label: t("cols.type"), width: "w-[80px] shrink-0" },
      { key: "workOrder", label: t("cols.workOrder"), width: "flex-1 min-w-0" },
      { key: "resolutionAmount", label: t("cols.resolutionAmount"), width: "w-[110px] shrink-0" },
      { key: "createdAt", label: t("cols.createdAt"), width: "w-[100px] shrink-0" },
      { key: "status", label: t("cols.status"), width: "w-[100px] shrink-0" },
    ],
    [t],
  );

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)]">
      <div className="flex h-[44px] items-center border-b border-[var(--border)] bg-[#F8FAFC]">
        {columns.map((col) => (
          <div
            key={col.key}
            className={`flex items-center px-3 ${col.width}`}
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
        const typeTone = TYPE_TONE[row.dispute_type] ?? { textColor: "#64748B", bgColor: "#F1F5F9" };
        const statusTone = STATUS_TONE[row.status] ?? { textColor: "#64748B", bgColor: "#F1F5F9" };
        const typeLabel = TYPE_KEY[row.dispute_type] ? t(TYPE_KEY[row.dispute_type]) : (row.dispute_type ?? "—");
        const statusLabel = STATUS_KEY[row.status] ? t(STATUS_KEY[row.status]) : (row.status ?? "—");
        const isSelected = selectedId === row.id;
        const linkedRef = row.work_order_id
          ? t("ref.workOrder", { id: row.work_order_id.slice(0, 8) })
          : row.invoice_id
            ? t("ref.invoice", { id: row.invoice_id.slice(0, 8) })
            : "—";
        return (
          <button
            key={row.id}
            type="button"
            onClick={() => onSelect?.(row.id)}
            className={`flex h-[48px] w-full items-center text-left ${
              isSelected ? "bg-[#EFF6FF]" : "bg-[var(--bg-surface)] hover:bg-[#F8FAFC]"
            } ${idx < items.length - 1 ? "border-b border-[var(--border)]" : ""}`}
          >
            <div className="flex w-[140px] shrink-0 items-center px-3">
              <span className="font-mono text-[12px] font-medium text-[var(--text-primary)]">
                {row.id.slice(0, 8)}
              </span>
            </div>

            <div className="flex w-[80px] shrink-0 items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: typeTone.textColor, backgroundColor: typeTone.bgColor }}
              >
                {typeLabel}
              </span>
            </div>

            <div className="flex min-w-0 flex-1 items-center px-3">
              <span className="truncate text-[13px] text-[var(--text-secondary)]">
                {linkedRef}
              </span>
            </div>

            <div className="flex w-[110px] shrink-0 items-center px-3">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {formatTwd(row.resolution_amount)}
              </span>
            </div>

            <div className="flex w-[100px] shrink-0 items-center px-3">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDate(row.created_at)}
              </span>
            </div>

            <div className="flex w-[100px] shrink-0 items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: statusTone.textColor, backgroundColor: statusTone.bgColor }}
              >
                {statusLabel}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
