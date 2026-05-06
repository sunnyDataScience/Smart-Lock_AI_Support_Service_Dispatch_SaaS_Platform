"use client";

import type { components } from "@/types/api.generated";

type Dispute = components["schemas"]["Dispute"];
type DisputeType = components["schemas"]["DisputeType"];
type DisputeStatus = components["schemas"]["DisputeStatus"];

interface Props {
  items: Dispute[];
  loading?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}

const typeConfig: Record<DisputeType, { label: string; textColor: string; bgColor: string }> = {
  pricing: { label: "價格", textColor: "#2563EB", bgColor: "#DBEAFE" },
  quality: { label: "品質", textColor: "#7C3AED", bgColor: "#EDE9FE" },
  warranty: { label: "保固", textColor: "#059669", bgColor: "#D1FAE5" },
  cancellation_fee: { label: "取消費", textColor: "#EA580C", bgColor: "#FFEDD5" },
  settlement: { label: "結算", textColor: "#DB2777", bgColor: "#FCE7F3" },
};

const statusConfig: Record<DisputeStatus, { label: string; textColor: string; bgColor: string }> = {
  filed: { label: "待處理", textColor: "#D97706", bgColor: "#FEF3C7" },
  in_review: { label: "調解中", textColor: "#2563EB", bgColor: "#DBEAFE" },
  resolved: { label: "已結案", textColor: "#059669", bgColor: "#D1FAE5" },
  rejected: { label: "已駁回", textColor: "#64748B", bgColor: "#F1F5F9" },
  closed: { label: "已關閉", textColor: "#374151", bgColor: "#E5E7EB" },
};

const columns = [
  { label: "爭議編號", width: "w-[140px] shrink-0" },
  { label: "類型", width: "w-[80px] shrink-0" },
  { label: "工單", width: "flex-1 min-w-0" },
  { label: "調解金額", width: "w-[110px] shrink-0" },
  { label: "建立日期", width: "w-[100px] shrink-0" },
  { label: "狀態", width: "w-[100px] shrink-0" },
];

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
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)]">
      <div className="flex h-[44px] items-center border-b border-[var(--border)] bg-[#F8FAFC]">
        {columns.map((col) => (
          <div
            key={col.label}
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
          載入中…
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
          尚無爭議案件
        </div>
      )}

      {items.map((row, idx) => {
        const type = typeConfig[row.dispute_type];
        const status = statusConfig[row.status];
        const isSelected = selectedId === row.id;
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
                style={{ color: type.textColor, backgroundColor: type.bgColor }}
              >
                {type.label}
              </span>
            </div>

            <div className="flex min-w-0 flex-1 items-center px-3">
              <span className="truncate text-[13px] text-[var(--text-secondary)]">
                {row.work_order_id ? `工單 ${row.work_order_id.slice(0, 8)}` : row.invoice_id ? `發票 ${row.invoice_id.slice(0, 8)}` : "—"}
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
                style={{ color: status.textColor, backgroundColor: status.bgColor }}
              >
                {status.label}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
