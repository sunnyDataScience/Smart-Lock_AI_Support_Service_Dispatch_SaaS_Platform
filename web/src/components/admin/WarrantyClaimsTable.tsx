"use client";

import type { components } from "@/types/api.generated";

type WarrantyClaim = components["schemas"]["WarrantyClaim"];
type WarrantyClaimStatus = components["schemas"]["WarrantyClaimStatus"];

interface Props {
  items: WarrantyClaim[];
  loading?: boolean;
}

const statusConfig: Record<WarrantyClaimStatus, { label: string; textColor: string; bgColor: string }> = {
  filed: { label: "已申請", textColor: "#92400E", bgColor: "#FEF3C7" },
  in_progress: { label: "處理中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  approved: { label: "已核准", textColor: "#065F46", bgColor: "#D1FAE5" },
  rejected: { label: "已拒絕", textColor: "#991B1B", bgColor: "#FEE2E2" },
  closed: { label: "已結案", textColor: "#374151", bgColor: "#E5E7EB" },
};

const columns = [
  { label: "案件編號", width: "w-[110px]" },
  { label: "設備", width: "w-[150px]" },
  { label: "保固起始日", width: "w-[100px]" },
  { label: "保固到期日", width: "w-[100px]" },
  { label: "剩餘天數", width: "w-[90px]" },
  { label: "保固期", width: "w-[80px]" },
  { label: "申請狀態", width: "w-[90px]" },
  { label: "折讓金額", width: "w-[100px]" },
  { label: "操作", width: "flex-1" },
];

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00").getTime();
  const today = new Date(new Date().toISOString().slice(0, 10) + "T00:00:00").getTime();
  return Math.round((target - today) / ONE_DAY_MS);
}

function remainingDisplay(remaining: number): { label: string; color: string; bold: boolean } {
  if (remaining < 0) {
    return { label: `已逾期 ${Math.abs(remaining)} 天`, color: "#DC2626", bold: true };
  }
  if (remaining === 0) {
    return { label: "今日到期", color: "#DC2626", bold: true };
  }
  if (remaining <= 30) {
    return { label: `${remaining} 天`, color: "#D97706", bold: true };
  }
  if (remaining <= 90) {
    return { label: `${remaining} 天`, color: "#D97706", bold: false };
  }
  return { label: `${remaining} 天`, color: "#059669", bold: false };
}

function periodBadge(isWithin: boolean, remaining: number): { label: string; textColor: string; bgColor: string } {
  if (!isWithin) return { label: "已過期", textColor: "#B91C1C", bgColor: "#FEE2E2" };
  if (remaining <= 30) return { label: "寬限期", textColor: "#92400E", bgColor: "#FEF3C7" };
  return { label: "有效", textColor: "#15803D", bgColor: "#DCFCE7" };
}

function formatTwd(amount: string | null | undefined): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function WarrantyClaimsTable({ items, loading }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[#F8FAFC] border-b border-[var(--border)]">
        {columns.map((col) => (
          <div key={col.label} className={`flex items-center px-3 ${col.width}`}>
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
          尚無保固申請
        </div>
      )}

      {items.map((row, idx) => {
        const remaining = daysUntil(row.warranty_end_date);
        const remainingUi = remainingDisplay(remaining);
        const period = periodBadge(row.is_within_warranty, remaining);
        const status = statusConfig[row.status];

        return (
          <div
            key={row.id}
            className={`flex h-[56px] items-center bg-[var(--bg-surface)] ${
              idx < items.length - 1 ? "border-b border-[var(--border)]" : ""
            }`}
          >
            <div className="flex w-[110px] items-center px-3">
              <span className="font-mono text-xs font-medium text-[var(--text-primary)]">
                {row.id.slice(0, 8)}
              </span>
            </div>

            <div className="flex w-[150px] flex-col justify-center px-3">
              <span className="truncate text-xs font-semibold text-[var(--text-primary)]">
                {row.device_brand}
              </span>
              <span className="truncate text-[11px] text-[var(--text-secondary)]">
                {row.device_model}
              </span>
            </div>

            <div className="flex w-[100px] items-center px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {row.warranty_start_date}
              </span>
            </div>

            <div className="flex w-[100px] items-center px-3">
              <span className="text-xs text-[var(--text-primary)]">
                {row.warranty_end_date}
              </span>
            </div>

            <div className="flex w-[90px] items-center px-3">
              <span
                className="text-xs"
                style={{ color: remainingUi.color, fontWeight: remainingUi.bold ? 700 : 600 }}
              >
                {remainingUi.label}
              </span>
            </div>

            <div className="flex w-[80px] items-center px-3">
              <span
                className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                style={{ color: period.textColor, backgroundColor: period.bgColor }}
              >
                {period.label}
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

            <div className="flex w-[100px] items-center px-3">
              <span className="font-mono text-[12px] text-[var(--text-primary)]">
                {formatTwd(row.discount_offered)}
              </span>
            </div>

            <div className="flex flex-1 items-center justify-end gap-[6px] px-3">
              <button
                disabled
                title="即將推出"
                className="cursor-not-allowed rounded-md border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)] opacity-60"
              >
                檢視詳情
              </button>
              {row.status === "filed" || row.status === "in_progress" ? (
                <button
                  disabled
                  title="即將推出"
                  className="cursor-not-allowed rounded-md bg-[var(--primary)] px-2 py-1 text-[11px] font-medium text-white opacity-60"
                >
                  核准保固
                </button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
