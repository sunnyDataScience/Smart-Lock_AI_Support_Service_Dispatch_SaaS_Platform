"use client";

import type { components } from "@/types/api.generated";

type Settlement = components["schemas"]["Settlement"];
type SettlementStatus = components["schemas"]["SettlementStatus"];

interface Props {
  items: Settlement[];
  loading?: boolean;
}

const statusConfig: Record<
  SettlementStatus,
  { label: string; textColor: string; bgColor: string }
> = {
  pending: { label: "待付款", textColor: "#B45309", bgColor: "#FEF3C7" },
  paid: { label: "已付款", textColor: "#10B981", bgColor: "#D1FAE5" },
  failed: { label: "付款失敗", textColor: "#B91C1C", bgColor: "#FEE2E2" },
};

const paymentMethodLabel: Record<NonNullable<Settlement["payment_method"]>, string> = {
  bank_transfer: "銀行轉帳",
  other: "其他",
};

const columns = [
  { label: "技師", width: "w-[150px] shrink-0" },
  { label: "金額", width: "w-[140px] shrink-0" },
  { label: "狀態", width: "w-[100px] shrink-0" },
  { label: "付款方式", width: "w-[110px] shrink-0" },
  { label: "付款時間", width: "w-[160px] shrink-0" },
  { label: "建立時間", width: "flex-1 min-w-[160px] min-w-0" },
];

function formatAmount(amount: string, currency: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `${currency} ${amount}`;
  return `${currency} ${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-TW", { hour12: false });
}

export default function SettlementTable({ items, loading }: Props) {
  return (
    <div className="flex min-w-0 flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Batch Action Bar — disabled until write endpoints land */}
      <div
        className="flex items-center gap-3 border-b border-[var(--border)] px-8 py-3 opacity-60"
        title="即將推出"
      >
        <div className="h-4 w-4 cursor-not-allowed rounded border-[1.5px] border-[var(--border)]" />
        <span className="text-[13px] text-[var(--text-disabled)]">全選</span>
        <button
          disabled
          title="即將推出"
          className="cursor-not-allowed rounded-md bg-[var(--primary)] px-4 py-[7px] text-[13px] font-semibold text-white"
        >
          批次確認
        </button>
        <button
          disabled
          title="即將推出"
          className="cursor-not-allowed rounded-md border border-[var(--border)] px-4 py-[7px] text-[13px] font-medium text-[var(--text-disabled)]"
        >
          批次標記已付
        </button>
      </div>

      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        {columns.map((col) => (
          <div
            key={col.label}
            className={`flex items-center px-2 ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Empty / Loading state */}
      {loading && items.length === 0 && (
        <div className="flex h-[160px] items-center justify-center text-sm text-[var(--text-secondary)]">
          載入中…
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[160px] items-center justify-center text-sm text-[var(--text-secondary)]">
          尚無結算資料
        </div>
      )}

      {/* Data Rows */}
      {items.map((s) => {
        const badge = statusConfig[s.status];
        const methodLabel = s.payment_method
          ? paymentMethodLabel[s.payment_method]
          : "—";
        return (
          <div
            key={s.id}
            className="flex h-[48px] items-center border-b border-[var(--border)] px-8"
          >
            {/* Technician */}
            <div className="flex w-[150px] shrink-0 items-center px-2">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {s.technician_name || s.technician_id.slice(0, 8)}
              </span>
            </div>

            {/* Amount */}
            <div className="flex w-[140px] shrink-0 items-center px-2">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {formatAmount(s.amount, s.currency)}
              </span>
            </div>

            {/* Status */}
            <div className="flex w-[100px] shrink-0 items-center px-2">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: badge.textColor, backgroundColor: badge.bgColor }}
              >
                {badge.label}
              </span>
            </div>

            {/* Payment Method */}
            <div className="flex w-[110px] shrink-0 items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {methodLabel}
              </span>
            </div>

            {/* Paid At */}
            <div className="flex w-[160px] shrink-0 items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDateTime(s.paid_at)}
              </span>
            </div>

            {/* Created At */}
            <div className="flex min-w-0 flex-1 min-w-[160px] items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDateTime(s.created_at)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
