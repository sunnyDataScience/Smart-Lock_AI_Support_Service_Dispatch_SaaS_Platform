"use client";

import Link from "next/link";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];
type Urgency = components["schemas"]["Urgency"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
}

type StatusGroup = "pending" | "dispatched" | "in_progress" | "done" | "cancelled";

const STATUS_GROUP_MAP: Record<WorkOrderStatus, StatusGroup> = {
  inquiring: "pending",
  qualified: "pending",
  quoted: "pending",
  negotiating: "pending",
  accepted: "dispatched",
  scheduled: "dispatched",
  dispatching: "dispatched",
  assigned: "dispatched",
  en_route: "dispatched",
  arrived: "dispatched",
  in_progress: "in_progress",
  completed: "done",
  billed: "done",
  paid: "done",
  closed: "done",
  cancelled: "cancelled",
};

const STATUS_GROUP_STYLE: Record<StatusGroup, { label: string; color: string; bg: string }> = {
  pending: { label: "待處理", color: "#6366F1", bg: "#EEF2FF" },
  dispatched: { label: "已派工", color: "#8B5CF6", bg: "#F5F3FF" },
  in_progress: { label: "處理中", color: "#3B82F6", bg: "#DBEAFE" },
  done: { label: "已完成", color: "#10B981", bg: "#D1FAE5" },
  cancelled: { label: "已取消", color: "#EF4444", bg: "#FEE2E2" },
};

const URGENCY_STYLE: Record<Urgency, { label: string; color: string; bg: string }> = {
  low: { label: "低", color: "#64748B", bg: "#F1F5F9" },
  medium: { label: "中", color: "#D97706", bg: "#FEF3C7" },
  high: { label: "高", color: "#EF4444", bg: "#FEE2E2" },
};

const columns = [
  { label: "工單 ID", width: "w-[120px]" },
  { label: "區/地址", width: "flex-1" },
  { label: "品牌", width: "w-[90px]" },
  { label: "型號", width: "w-[110px]" },
  { label: "狀態", width: "w-[80px]" },
  { label: "緊急度", width: "w-[70px]" },
  { label: "估價", width: "w-[100px]" },
  { label: "建立時間", width: "w-[90px]" },
];

function shortId(id: string): string {
  return id.slice(0, 8);
}

function formatPrice(value?: string | null): string {
  if (!value) return "—";
  const n = parseFloat(value);
  if (Number.isNaN(n)) return "—";
  return `NT$ ${n.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

export default function WorkOrdersTable({ items, loading }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
        {columns.map((col) => (
          <div key={col.label} className={`${col.width} px-0`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {items.length === 0 && !loading && (
        <div className="flex h-24 items-center justify-center">
          <span className="text-[13px] text-[var(--text-secondary)]">目前無資料</span>
        </div>
      )}

      {items.map((order, idx) => {
        const group = STATUS_GROUP_MAP[order.status];
        const statusStyle = STATUS_GROUP_STYLE[group];
        const urgencyStyle = URGENCY_STYLE[order.urgency];
        const districtAddr = order.district
          ? order.address.startsWith(order.district)
            ? order.address
            : `${order.district} · ${order.address}`
          : order.address || "—";
        return (
          <Link
            key={order.id}
            href={`/work-orders/${order.id}`}
            className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] ${
              idx % 2 === 0 ? "bg-white" : "bg-[var(--bg-page)]"
            }`}
          >
            <div className="w-[120px]">
              <span className="font-mono text-[12px] text-[var(--primary)]" title={order.id}>
                {shortId(order.id)}
              </span>
            </div>
            <div className="flex-1 truncate pr-4">
              <span className="text-[13px] text-[var(--text-primary)]">{districtAddr}</span>
            </div>
            <div className="w-[90px]">
              <span className="text-[13px] text-[var(--text-primary)]">
                {order.brand || "—"}
              </span>
            </div>
            <div className="w-[110px]">
              <span className="text-[13px] text-[var(--text-primary)]">
                {order.model || "—"}
              </span>
            </div>
            <div className="w-[80px]">
              <span
                className="rounded-full px-[10px] py-1 text-[11px] font-medium"
                style={{ color: statusStyle.color, backgroundColor: statusStyle.bg }}
              >
                {statusStyle.label}
              </span>
            </div>
            <div className="w-[70px]">
              <span
                className="rounded px-2 py-1 text-[11px] font-medium"
                style={{ color: urgencyStyle.color, backgroundColor: urgencyStyle.bg }}
              >
                {urgencyStyle.label}
              </span>
            </div>
            <div className="w-[100px]">
              <span className="text-[13px] text-[var(--text-primary)]">
                {formatPrice(order.estimated_reward)}
              </span>
            </div>
            <div className="w-[90px]">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {formatRelative(order.created_at)}
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

export { STATUS_GROUP_MAP, STATUS_GROUP_STYLE, URGENCY_STYLE };
