"use client";

import Link from "next/link";
import { Eye } from "lucide-react";
import type { components } from "@/types/api.generated";
import { formatRelative } from "@/lib/format";

type Invoice = components["schemas"]["Invoice"];
type InvoiceStatus = components["schemas"]["InvoiceStatus"];

interface Props {
  items: Invoice[];
  loading?: boolean;
}

const statusConfig: Record<InvoiceStatus, { label: string; textColor: string; bgColor: string }> = {
  pending: { label: "待開立", textColor: "#92400E", bgColor: "#FEF3C7" },
  issued: { label: "已開立", textColor: "#065F46", bgColor: "#D1FAE5" },
  allowance_pending: { label: "折讓處理中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  voided: { label: "作廢", textColor: "#991B1B", bgColor: "#FEE2E2" },
  reopened: { label: "重開立", textColor: "#5B21B6", bgColor: "#EDE9FE" },
};

const columns = [
  { label: "發票編號", width: "w-[140px]" },
  { label: "工單", width: "w-[120px]" },
  { label: "金額", width: "w-[140px]" },
  { label: "稅務分類", width: "w-[110px]" },
  { label: "狀態", width: "w-[110px]" },
  { label: "開立時間", width: "w-[160px]" },
  { label: "更新時間", width: "w-[160px]" },
  { label: "操作", width: "flex-1" },
];

function formatTwd(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const categoryLabel: Record<string, string> = {
  service_fee: "服務費",
  travel_fee: "車馬費",
  parts: "零件",
  other: "其他",
};

export default function InvoicesTable({ items, loading }: Props) {
  return (
    <div className="flex flex-1 flex-col bg-[var(--bg-surface)]">
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
          載入中…
        </div>
      )}
      {!loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
          尚無發票紀錄
        </div>
      )}

      {/* Data Rows */}
      {items.map((inv) => {
        const badge = statusConfig[inv.status];
        const isVoided = inv.status === "voided";

        return (
          <div
            key={inv.id}
            className={`flex h-[52px] items-center border-b border-[var(--border)] px-8 ${
              isVoided ? "border-l-[3px] border-l-[#EF4444] bg-[#FEF2F2]" : ""
            }`}
          >
            {/* Invoice Number */}
            <div className="flex w-[140px] items-center px-2">
              <span className="font-['IBM_Plex_Mono'] text-[13px] font-medium text-[var(--text-primary)]">
                {inv.invoice_number}
              </span>
            </div>

            {/* Work Order */}
            <div className="flex w-[120px] items-center px-2">
              <Link
                href={`/work-orders/${inv.work_order_id}`}
                className="font-mono text-[13px] font-medium text-[var(--primary)] hover:underline"
              >
                {inv.work_order_id.slice(0, 8)}
              </Link>
            </div>

            {/* Amount */}
            <div className="flex w-[140px] items-center px-2">
              <span className="font-['IBM_Plex_Mono'] text-[13px] font-semibold text-[var(--text-primary)]">
                {formatTwd(inv.amount)}
              </span>
            </div>

            {/* Tax Category */}
            <div className="flex w-[110px] items-center px-2">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {inv.category ? categoryLabel[inv.category] ?? inv.category : "—"}
              </span>
            </div>

            {/* Status */}
            <div className="flex w-[110px] items-center px-2">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: badge.textColor, backgroundColor: badge.bgColor }}
              >
                {badge.label}
              </span>
            </div>

            {/* Issued At */}
            <div className="flex w-[160px] items-center px-2">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {inv.issued_at ? formatRelative(inv.issued_at) : "—"}
              </span>
            </div>

            {/* Updated At */}
            <div className="flex w-[160px] items-center px-2">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {inv.updated_at ? formatRelative(inv.updated_at) : "—"}
              </span>
            </div>

            {/* Actions */}
            <div className="flex flex-1 items-center gap-1 px-2">
              <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
