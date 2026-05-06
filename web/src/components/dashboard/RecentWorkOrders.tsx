"use client";

import Link from "next/link";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
  URGENCY_STYLE,
} from "@/components/work-orders/WorkOrdersTable";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
  error?: string | null;
}

const columns = [
  { key: "id", label: "工單 ID", width: "w-[110px]" },
  { key: "address", label: "區/地址", width: "flex-1" },
  { key: "device", label: "品牌/型號", width: "w-[160px]" },
  { key: "status", label: "狀態", width: "w-[90px]" },
  { key: "urgency", label: "緊急度", width: "w-[70px]" },
  { key: "createdAt", label: "建立時間", width: "w-[100px]" },
  { key: "technician", label: "指派技師", width: "w-[110px]" },
] as const;

function shortId(id: string): string {
  return id.slice(0, 8);
}

function technicianTag(technicianId: string | null | undefined): string | null {
  if (!technicianId) return null;
  return `技師 ${technicianId.slice(0, 4)}`;
}

export default function RecentWorkOrders({ items, loading, error }: Props) {
  return (
    <section
      aria-labelledby="recent-work-orders-heading"
      className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]"
    >
      <div className="flex items-center justify-between px-5 py-4">
        <h3
          id="recent-work-orders-heading"
          className="text-[18px] font-bold text-[#18181B]"
        >
          最近工單
        </h3>
        <Link
          href="/work-orders"
          className="text-[14px] font-medium text-[var(--primary)] hover:underline focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 rounded"
        >
          查看全部 →
        </Link>
      </div>

      <div
        role="table"
        aria-labelledby="recent-work-orders-heading"
        aria-rowcount={items.length + 1}
      >
      <div role="row" className="flex bg-[#F1F5F9] px-5 py-[10px]">
        {columns.map((col) => (
          <div
            key={col.key}
            role="columnheader"
            aria-sort="none"
            className={col.width}
          >
            <span className="text-[12px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {error && (
        <div className="border-b border-red-200 bg-red-50 px-5 py-3 text-[12px] text-red-700">
          載入工單失敗：{error}
        </div>
      )}

      {loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-[13px] text-[var(--text-secondary)]">
          載入中…
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className="flex h-[120px] items-center justify-center text-[13px] text-[var(--text-secondary)]">
          目前沒有工單
        </div>
      )}

      {items.map((order, idx) => {
        const group = STATUS_GROUP_MAP[order.status];
        const status = STATUS_GROUP_STYLE[group];
        const urgency = URGENCY_STYLE[order.urgency];
        const districtAddr = order.district || order.address || "—";
        const tech = technicianTag(order.technician_id);
        return (
          <div key={order.id}>
            <Link
              href={`/work-orders/${order.id}`}
              role="row"
              aria-rowindex={idx + 2}
              className={`flex items-center px-5 py-3 hover:bg-[#EFF6FF] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-inset ${
                idx % 2 === 1 ? "bg-[var(--bg-page)]" : "bg-white"
              }`}
            >
              <div role="cell" className="w-[110px]">
                <span
                  className="font-mono text-[13px] font-medium text-[var(--primary)]"
                  title={order.id}
                >
                  {shortId(order.id)}
                </span>
              </div>
              <div role="cell" className="flex-1 truncate pr-3">
                <span
                  className="text-[13px] text-[#18181B]"
                  title={order.address}
                >
                  {districtAddr}
                </span>
              </div>
              <div role="cell" className="w-[160px] truncate pr-3">
                <span className="text-[13px] text-[#18181B]">
                  {order.brand || "—"} {order.model || ""}
                </span>
              </div>
              <div role="cell" className="w-[90px]">
                <span
                  className="rounded-full px-[10px] py-[2px] text-[11px] font-medium"
                  style={{ color: status.color, backgroundColor: status.bg }}
                >
                  {status.label}
                </span>
              </div>
              <div role="cell" className="w-[70px]">
                <span
                  className="rounded px-2 py-[2px] text-[11px] font-medium"
                  style={{ color: urgency.color, backgroundColor: urgency.bg }}
                >
                  {urgency.label}
                </span>
              </div>
              <div role="cell" className="w-[100px]">
                <span className="text-[12px] text-[var(--text-tertiary)]">
                  {formatRelative(order.created_at)}
                </span>
              </div>
              <div role="cell" className="w-[110px]">
                <span className="text-[13px] text-[#18181B]">
                  {tech ?? <span className="text-[var(--text-disabled)]">未指派</span>}
                </span>
              </div>
            </Link>
            {idx < items.length - 1 && <div className="h-px bg-[#E4E4E7]" />}
          </div>
        );
      })}
      </div>{/* /role="table" */}

      {items.length > 0 && (
        <>
          <div className="h-px bg-[#E4E4E7]" />
          <div className="flex justify-center px-5 py-3">
            <span className="text-[12px] text-[var(--text-disabled)]">
              顯示最近 {items.length} 筆
            </span>
          </div>
        </>
      )}
    </section>
  );
}
