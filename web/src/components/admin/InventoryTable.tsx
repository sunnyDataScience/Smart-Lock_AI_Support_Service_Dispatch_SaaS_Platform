"use client";

import type { components } from "@/types/api.generated";

type InventoryItem = components["schemas"]["InventoryItem"];
type StockStatus = components["schemas"]["InventoryStockStatus"];

interface Props {
  items: InventoryItem[];
  loading?: boolean;
}

const STATUS_BADGE: Record<
  StockStatus,
  { label: string; textColor: string; bgColor: string } | null
> = {
  in_stock: null,
  low_stock: { label: "低庫存", textColor: "#B45309", bgColor: "#FFFBEB" },
  out_of_stock: { label: "缺貨", textColor: "#DC2626", bgColor: "#FEF2F2" },
};

const columns = [
  { label: "物料名稱", width: "w-[200px] shrink-0" },
  { label: "料號", width: "w-[140px] shrink-0" },
  { label: "類別", width: "w-[120px] shrink-0" },
  { label: "當前庫存", width: "w-[150px] shrink-0" },
  { label: "安全庫存", width: "w-[100px] shrink-0" },
  { label: "最後補貨", width: "w-[140px] shrink-0" },
  { label: "操作", width: "flex-1 min-w-0" },
];

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

export default function InventoryTable({ items, loading }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
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

      {loading && items.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          載入中…
        </div>
      ) : items.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
          尚無庫存品項
        </div>
      ) : (
        items.map((row, idx) => {
          const badge = STATUS_BADGE[row.stock_status];
          const stockColor =
            row.stock_status === "out_of_stock"
              ? "text-[#DC2626]"
              : row.stock_status === "low_stock"
                ? "text-[#B45309]"
                : "text-[var(--text-primary)]";
          return (
            <div
              key={row.id}
              className={`flex h-[52px] items-center bg-[var(--bg-surface)] ${
                idx < items.length - 1
                  ? "border-b border-[var(--border)]"
                  : ""
              }`}
            >
              <div className="flex w-[200px] shrink-0 items-center px-3">
                <span className="truncate text-[13px] font-medium text-[var(--text-primary)]">
                  {row.name}
                </span>
              </div>

              <div className="flex w-[140px] shrink-0 items-center px-3">
                <span className="font-mono text-xs text-[var(--text-secondary)]">
                  {row.part_number}
                </span>
              </div>

              <div className="flex w-[120px] shrink-0 items-center px-3">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {row.category}
                </span>
              </div>

              <div className="flex w-[150px] shrink-0 items-center gap-2 px-3">
                <span className={`text-[13px] font-semibold ${stockColor}`}>
                  {row.quantity_on_hand}
                </span>
                {badge && (
                  <span
                    className="rounded-[10px] px-2 py-[2px] text-[11px] font-semibold"
                    style={{
                      color: badge.textColor,
                      backgroundColor: badge.bgColor,
                    }}
                  >
                    {badge.label}
                  </span>
                )}
              </div>

              <div className="flex w-[100px] shrink-0 items-center px-3">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {row.reorder_point}
                </span>
              </div>

              <div className="flex w-[140px] shrink-0 items-center px-3">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  {formatDate(row.last_restocked_at)}
                </span>
              </div>

              <div className="flex min-w-0 flex-1 items-center justify-end gap-[6px] px-3">
                <button
                  disabled
                  title="即將推出（需 inventory_transactions 寫入端點）"
                  className="cursor-not-allowed rounded-md bg-[var(--primary)] px-3 py-[5px] text-xs font-medium text-white opacity-50"
                >
                  補貨
                </button>
                <button
                  disabled
                  title="即將推出"
                  className="cursor-not-allowed rounded-md border border-[var(--border)] px-3 py-[5px] text-xs font-medium text-[var(--text-secondary)] opacity-50"
                >
                  編輯
                </button>
                <button
                  disabled
                  title="即將推出"
                  className="cursor-not-allowed rounded-md border border-[var(--border)] px-3 py-[5px] text-xs font-medium text-[var(--text-secondary)] opacity-50"
                >
                  紀錄
                </button>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
