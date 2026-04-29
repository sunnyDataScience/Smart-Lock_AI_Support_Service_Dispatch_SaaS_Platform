"use client";

import type { components } from "@/types/api.generated";

type Reconciliation = components["schemas"]["Reconciliation"];

interface Props {
  items: Reconciliation[];
  loading?: boolean;
  onApprove?: (recon: Reconciliation) => void;
  pendingApproveId?: string | null;
}

const columns = [
  { label: "ID", width: "w-[100px]" },
  { label: "技師", width: "w-[140px]" },
  { label: "結算期間", width: "w-[200px]" },
  { label: "工單數", width: "w-[80px]", align: "text-right" as const },
  { label: "營收", width: "w-[110px]", align: "text-right" as const },
  { label: "平台費", width: "w-[110px]", align: "text-right" as const },
  { label: "技師應領", width: "w-[120px]", align: "text-right" as const },
  { label: "狀態", width: "w-[90px]" },
  { label: "操作", width: "flex-1" },
];

const statusConfig: Record<
  components["schemas"]["ReconciliationStatus"],
  { label: string; textColor: string; bgColor: string }
> = {
  pending: { label: "待核准", textColor: "#92400E", bgColor: "#FEF3C7" },
  approved: { label: "已核准", textColor: "#065F46", bgColor: "#D1FAE5" },
  disputed: { label: "爭議中", textColor: "#991B1B", bgColor: "#FEE2E2" },
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
          載入中…
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
          目前沒有對帳記錄
        </div>
      )}

      {items.map((row, idx) => {
        const status = statusConfig[row.status];
        const canApprove = row.status === "pending" && !!onApprove;
        return (
          <div
            key={row.id}
            className={`flex h-[56px] items-center bg-[var(--bg-surface)] ${
              idx < items.length - 1 ? "border-b border-[var(--border)]" : ""
            }`}
          >
            <div className="flex w-[100px] items-center px-3">
              <span className="font-mono text-xs text-[var(--text-primary)]">
                {row.id.slice(0, 8)}
              </span>
            </div>
            <div className="flex w-[140px] items-center px-3">
              <span className="truncate text-xs font-medium text-[var(--text-primary)]">
                {row.technician_name ?? row.technician_id.slice(0, 8)}
              </span>
            </div>
            <div className="flex w-[200px] items-center px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {formatPeriod(row.period_start, row.period_end)}
              </span>
            </div>
            <div className="flex w-[80px] items-center justify-end px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {row.total_orders}
              </span>
            </div>
            <div className="flex w-[110px] items-center justify-end px-3">
              <span className="font-mono text-[12px] text-[var(--text-primary)]">
                {formatTwd(row.total_revenue)}
              </span>
            </div>
            <div className="flex w-[110px] items-center justify-end px-3">
              <span className="font-mono text-[12px] text-[var(--text-secondary)]">
                {formatTwd(row.platform_fee)}
              </span>
            </div>
            <div className="flex w-[120px] items-center justify-end px-3">
              <span className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">
                {formatTwd(row.technician_payout)}
              </span>
            </div>
            <div className="flex w-[90px] items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: status.textColor, backgroundColor: status.bgColor }}
              >
                {status.label}
              </span>
            </div>
            <div className="flex flex-1 items-center justify-end gap-[6px] px-3">
              {canApprove ? (
                <button
                  onClick={() => onApprove!(row)}
                  disabled={pendingApproveId !== null && pendingApproveId !== undefined}
                  className="rounded-md bg-[var(--success)] px-2 py-1 text-[11px] font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pendingApproveId === row.id ? "處理中…" : "核准對帳"}
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
