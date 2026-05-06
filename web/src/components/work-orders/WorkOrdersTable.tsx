"use client";

import { useRef } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];
type Urgency = components["schemas"]["Urgency"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
}

// 每列固定高度（h-12 = 48px），virtualizer 需要精確值算 viewport
const ROW_HEIGHT = 48;
// 列數超過此門檻才啟用虛擬化，避免 wrapper 對短列表的 layout 副作用
const VIRTUALIZE_THRESHOLD = 50;
// 虛擬化模式的可視高度（單頁 ~12 列 + buffer）
const VIRTUAL_VIEWPORT_HEIGHT = 600;

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

// 工單狀態色彩：用 globals.css semantic token，視覺與 StatusBadge 對齊。
// pending/dispatched 用各自的紫/藍區分階段（不在 badge token 內，保留 hex）；
// 其餘用統一的 --badge-{tone} 變數。
const STATUS_GROUP_STYLE: Record<StatusGroup, { label: string; color: string; bg: string }> = {
  pending: { label: "待處理", color: "#6366F1", bg: "#EEF2FF" },
  dispatched: { label: "已派工", color: "#8B5CF6", bg: "#F5F3FF" },
  in_progress: { label: "處理中", color: "var(--badge-info-fg)", bg: "var(--badge-info-bg)" },
  done: { label: "已完成", color: "var(--badge-success-fg)", bg: "var(--badge-success-bg)" },
  cancelled: { label: "已取消", color: "var(--badge-danger-fg)", bg: "var(--badge-danger-bg)" },
};

const URGENCY_STYLE: Record<Urgency, { label: string; color: string; bg: string }> = {
  low: { label: "低", color: "var(--badge-muted-fg)", bg: "var(--badge-muted-bg)" },
  medium: { label: "中", color: "var(--badge-warn-fg)", bg: "var(--badge-warn-bg)" },
  high: { label: "高", color: "var(--badge-danger-fg)", bg: "var(--badge-danger-bg)" },
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

/**
 * 渲染單列工單（共用 short list 與虛擬化兩條路徑）。
 * style prop 給虛擬化模式用（absolute positioning），short list 不傳。
 */
function WorkOrderRow({
  order,
  idx,
  style,
}: {
  order: WorkOrder;
  idx: number;
  style?: React.CSSProperties;
}) {
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
      href={`/work-orders/${order.id}`}
      style={style}
      className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 focus-visible:ring-inset ${
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
}

function TableHeader() {
  return (
    <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
      {columns.map((col) => (
        <div key={col.label} className={`${col.width} px-0`}>
          <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
            {col.label}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * 虛擬化版本（>= VIRTUALIZE_THRESHOLD 列）— 用 @tanstack/react-virtual
 * 在固定高度 viewport 內只渲染可見的 ~12 列 + overscan 5 列。
 */
function VirtualizedRows({ items }: { items: WorkOrder[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
  });

  return (
    <div
      ref={parentRef}
      className="overflow-auto"
      style={{ height: `${VIRTUAL_VIEWPORT_HEIGHT}px` }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((vi) => {
          const order = items[vi.index];
          return (
            <WorkOrderRow
              key={order.id}
              order={order}
              idx={vi.index}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${vi.start}px)`,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function WorkOrdersTable({ items, loading }: Props) {
  const useVirtual = items.length >= VIRTUALIZE_THRESHOLD;

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <TableHeader />

      {items.length === 0 && !loading && (
        <div className="flex h-24 items-center justify-center">
          <span className="text-[13px] text-[var(--text-secondary)]">目前無資料</span>
        </div>
      )}

      {useVirtual ? (
        <VirtualizedRows items={items} />
      ) : (
        items.map((order, idx) => (
          <WorkOrderRow key={order.id} order={order} idx={idx} />
        ))
      )}
    </div>
  );
}

export { STATUS_GROUP_MAP, STATUS_GROUP_STYLE, URGENCY_STYLE };
