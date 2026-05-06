"use client";

import Link from "next/link";
import type { components } from "@/types/api.generated";
import { formatRelative } from "@/lib/format";

type RefundRequest = components["schemas"]["RefundRequest"];
type RefundRequestStatus = components["schemas"]["RefundRequestStatus"];
type Decision = "approve" | "reject" | "escalate";

interface Props {
  items: RefundRequest[];
  loading?: boolean;
  onDecide?: (refund: RefundRequest, decision: Decision) => void;
  pendingId?: string | null;
}

const statusConfig: Record<RefundRequestStatus, { label: string; textColor: string; bgColor: string }> = {
  pending: { label: "待審核", textColor: "#92400E", bgColor: "#FEF3C7" },
  csm_approved: { label: "等候第二簽", textColor: "#7C2D12", bgColor: "#FED7AA" },
  approved: { label: "已核准", textColor: "#065F46", bgColor: "#D1FAE5" },
  rejected: { label: "已拒絕", textColor: "#991B1B", bgColor: "#FEE2E2" },
  escalated: { label: "已升級", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  executed: { label: "已完款", textColor: "#374151", bgColor: "#E5E7EB" },
  cancelled: { label: "已取消", textColor: "#374151", bgColor: "#E5E7EB" },
};

const columns = [
  { label: "退款編號", width: "w-[120px]" },
  { label: "關聯工單", width: "w-[120px]" },
  { label: "金額", width: "w-[120px]" },
  { label: "退款原因", width: "flex-[2]" },
  { label: "雙簽", width: "w-[60px]" },
  { label: "審批進度", width: "w-[100px]" },
  { label: "狀態", width: "w-[110px]" },
  { label: "申請時間", width: "w-[150px]" },
  { label: "操作", width: "w-[160px]" },
];

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
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center rounded-t-lg bg-[#F1F5F9]">
        {columns.map((col) => (
          <div
            key={col.label}
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
          載入中…
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
          尚無退款申請
        </div>
      )}

      {items.map((row) => {
        const badge = statusConfig[row.status];
        const urgent = isUrgentStatus(row.status);
        const chainLength = Array.isArray(row.approval_chain) ? row.approval_chain.length : 0;
        const isClosed = row.status === "executed" || row.status === "cancelled" || row.status === "rejected";

        return (
          <div
            key={row.id}
            className={`flex h-[56px] items-center border-b border-[var(--border)] last:border-b-0 ${
              urgent ? "bg-[#FEF2F2]" : ""
            }`}
          >
            <div className="flex w-[120px] items-center px-[10px]">
              <span className="font-mono text-xs text-[var(--text-primary)]">
                {row.id.slice(0, 8)}
              </span>
            </div>

            <div className="flex w-[120px] items-center px-[10px]">
              <Link
                href={`/work-orders/${row.work_order_id}`}
                className="font-mono text-xs text-[var(--primary)] hover:underline"
              >
                {row.work_order_id.slice(0, 8)}
              </Link>
            </div>

            <div className="flex w-[120px] items-center px-[10px]">
              <span className="font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                {formatTwd(row.amount)}
              </span>
            </div>

            <div className="flex flex-[2] items-center px-[10px]">
              <span className="line-clamp-1 text-xs text-[var(--text-primary)]" title={row.reason}>
                {row.reason}
              </span>
            </div>

            <div className="flex w-[60px] items-center justify-center px-[6px]">
              {row.requires_dual_sign ? (
                <span className="rounded bg-[#FEE2E2] px-2 py-[2px] text-[10px] font-medium text-[#991B1B]">
                  需
                </span>
              ) : (
                <span className="text-[11px] text-[var(--text-secondary)]">—</span>
              )}
            </div>

            <div className="flex w-[100px] items-center justify-center px-[6px]">
              <span className="text-xs text-[var(--text-secondary)]">
                {chainLength === 0 ? "未啟動" : `${chainLength} 步`}
              </span>
            </div>

            <div className="flex w-[110px] items-center justify-center px-[6px]">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: badge.textColor, backgroundColor: badge.bgColor }}
              >
                {badge.label}
              </span>
            </div>

            <div className="flex w-[150px] items-center px-[10px]">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {row.created_at ? formatRelative(row.created_at) : "—"}
              </span>
            </div>

            <div className="flex w-[160px] items-center justify-center gap-[6px] px-[6px]">
              {isClosed || row.status === "approved" ? (
                <span className="rounded-md bg-[#E2E8F0] px-3 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                  {row.status === "executed"
                    ? "已完款"
                    : row.status === "approved"
                      ? "已核准"
                      : row.status === "rejected"
                        ? "已拒絕"
                        : "已取消"}
                </span>
              ) : row.status === "pending" || row.status === "csm_approved" ? (
                <>
                  <button
                    onClick={() => onDecide?.(row, "approve")}
                    disabled={!onDecide || pendingId === row.id}
                    className="rounded-md bg-[var(--primary)] px-3 py-1 text-[11px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    title={
                      row.status === "csm_approved"
                        ? "第二簽核准（必須是不同 user）"
                        : row.requires_dual_sign
                          ? "首次核准（之後須第二簽）"
                          : "核准"
                    }
                  >
                    {row.status === "csm_approved" ? "第二簽" : "核准"}
                  </button>
                  <button
                    onClick={() => onDecide?.(row, "reject")}
                    disabled={!onDecide || pendingId === row.id}
                    className="rounded-md bg-[#EF4444] px-3 py-1 text-[11px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    拒絕
                  </button>
                </>
              ) : (
                <span className="rounded-md bg-[#DBEAFE] px-3 py-1 text-[11px] font-medium text-[#1E40AF]">
                  已升級
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
