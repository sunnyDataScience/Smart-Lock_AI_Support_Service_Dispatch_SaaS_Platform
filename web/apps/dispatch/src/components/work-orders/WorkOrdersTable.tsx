"use client";

import { useMemo, useRef } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { formatRelative } from "@shared/lib/format";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";

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

export type StatusGroup = "pending" | "dispatched" | "in_progress" | "done" | "cancelled";

export const STATUS_GROUP_MAP: Record<WorkOrderStatus, StatusGroup> = {
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

// Tone（顏色 token）與 label（i18n 字串）已分離。
// 視覺常數模組級不變；label 由各元件自行 useTranslations 取得。
export const STATUS_GROUP_TONE: Record<StatusGroup, { color: string; bg: string }> = {
  pending: { color: "#6366F1", bg: "#EEF2FF" },
  dispatched: { color: "#8B5CF6", bg: "#F5F3FF" },
  in_progress: { color: "var(--badge-info-fg)", bg: "var(--badge-info-bg)" },
  done: { color: "var(--badge-success-fg)", bg: "var(--badge-success-bg)" },
  cancelled: { color: "var(--badge-danger-fg)", bg: "var(--badge-danger-bg)" },
};

export const URGENCY_TONE: Record<Urgency, { color: string; bg: string }> = {
  low: { color: "var(--badge-muted-fg)", bg: "var(--badge-muted-bg)" },
  medium: { color: "var(--badge-warn-fg)", bg: "var(--badge-warn-bg)" },
  high: { color: "var(--badge-danger-fg)", bg: "var(--badge-danger-bg)" },
};

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
  groupLabel,
  urgencyLabel,
}: {
  order: WorkOrder;
  idx: number;
  style?: React.CSSProperties;
  groupLabel: string;
  urgencyLabel: string;
}) {
  const group = STATUS_GROUP_MAP[order.status];
  const groupTone = STATUS_GROUP_TONE[group];
  const urgencyTone = URGENCY_TONE[order.urgency];
  const districtAddr = order.district
    ? order.address.startsWith(order.district)
      ? order.address
      : `${order.district} · ${order.address}`
    : order.address || "—";
  return (
    <Link
      href={`/work-orders/${order.id}`}
      role="row"
      aria-rowindex={idx + 2}  /* +1 表頭、+1 to be 1-indexed */
      style={style}
      className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 focus-visible:ring-inset ${
        idx % 2 === 0 ? "bg-white" : "bg-[var(--bg-page)]"
      }`}
    >
      <div role="cell" className="w-[120px]">
        {/* CR-0020：顯示公單號 document_number（{2碼地區}-{6碼流水}）;
            不掛 title={order.id}（避免洩漏內部 UUID,同 A6）。 */}
        <span className="font-mono text-[12px] text-[var(--primary)]">
          {order.document_number ?? shortId(order.id)}
        </span>
      </div>
      <div role="cell" className="flex-1 truncate pr-4">
        <span className="text-[13px] text-[var(--text-primary)]">{districtAddr}</span>
      </div>
      <div role="cell" className="w-[90px]">
        <span className="text-[13px] text-[var(--text-primary)]">
          {order.brand || "—"}
        </span>
      </div>
      <div role="cell" className="w-[110px]">
        <span className="text-[13px] text-[var(--text-primary)]">
          {order.model || "—"}
        </span>
      </div>
      <div role="cell" className="w-[80px]">
        <span
          className="rounded-full px-[10px] py-1 text-[11px] font-medium"
          style={{ color: groupTone.color, backgroundColor: groupTone.bg }}
        >
          {groupLabel}
        </span>
      </div>
      <div role="cell" className="w-[70px]">
        <span
          className="rounded px-2 py-1 text-[11px] font-medium"
          style={{ color: urgencyTone.color, backgroundColor: urgencyTone.bg }}
        >
          {urgencyLabel}
        </span>
      </div>
      <div role="cell" className="w-[100px]">
        <span className="text-[13px] text-[var(--text-primary)]">
          {formatPrice(order.estimated_reward)}
        </span>
      </div>
      <div role="cell" className="w-[90px]">
        <span className="text-[12px] text-[var(--text-secondary)]">
          {formatRelative(order.created_at)}
        </span>
      </div>
    </Link>
  );
}

function TableHeader({ cols }: { cols: { key: string; label: string; width: string }[] }) {
  return (
    <div role="row" className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
      {cols.map((col) => (
        <div
          key={col.key}
          role="columnheader"
          aria-sort="none"  /* 之後加排序時改 ascending/descending */
          className={`${col.width} px-0`}
        >
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
function VirtualizedRows({
  items,
  groupLabels,
  urgencyLabels,
}: {
  items: WorkOrder[];
  groupLabels: Record<StatusGroup, string>;
  urgencyLabels: Record<Urgency, string>;
}) {
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
              groupLabel={groupLabels[STATUS_GROUP_MAP[order.status]]}
              urgencyLabel={urgencyLabels[order.urgency]}
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
  const tCols = useTranslations("tables.workOrders.cols");
  const tTable = useTranslations("tables.workOrders");
  const tEmpty = useTranslations("tables");
  const tGroup = useTranslations("status.workOrderGroup");
  const tUrgency = useTranslations("urgency");

  const cols = useMemo(
    () => [
      { key: "id", label: tCols("id"), width: "w-[120px]" },
      { key: "address", label: tCols("address"), width: "flex-1" },
      { key: "brand", label: tCols("brand"), width: "w-[90px]" },
      { key: "model", label: tCols("model"), width: "w-[110px]" },
      { key: "status", label: tCols("status"), width: "w-[80px]" },
      { key: "urgency", label: tCols("urgency"), width: "w-[70px]" },
      { key: "estimate", label: tCols("estimate"), width: "w-[100px]" },
      { key: "createdAt", label: tCols("createdAt"), width: "w-[90px]" },
    ],
    [tCols],
  );

  const groupLabels: Record<StatusGroup, string> = useMemo(
    () => ({
      pending: tGroup("pending"),
      dispatched: tGroup("dispatched"),
      in_progress: tGroup("in_progress"),
      done: tGroup("done"),
      cancelled: tGroup("cancelled"),
    }),
    [tGroup],
  );

  const urgencyLabels: Record<Urgency, string> = useMemo(
    () => ({
      low: tUrgency("low"),
      medium: tUrgency("medium"),
      high: tUrgency("high"),
    }),
    [tUrgency],
  );

  const useVirtual = items.length >= VIRTUALIZE_THRESHOLD;

  return (
    <div
      role="table"
      aria-label={tTable("ariaLabel")}
      aria-rowcount={items.length + 1}  /* 含表頭 */
      aria-colcount={cols.length}
      className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]"
    >
      <TableHeader cols={cols} />

      {items.length === 0 && !loading && (
        <div role="row" className="flex h-24 items-center justify-center">
          <div role="cell" aria-colspan={cols.length}>
            <span className="text-[13px] text-[var(--text-secondary)]">{tEmpty("empty")}</span>
          </div>
        </div>
      )}

      {useVirtual ? (
        <VirtualizedRows items={items} groupLabels={groupLabels} urgencyLabels={urgencyLabels} />
      ) : (
        items.map((order, idx) => (
          <WorkOrderRow
            key={order.id}
            order={order}
            idx={idx}
            groupLabel={groupLabels[STATUS_GROUP_MAP[order.status]]}
            urgencyLabel={urgencyLabels[order.urgency]}
          />
        ))
      )}
    </div>
  );
}
