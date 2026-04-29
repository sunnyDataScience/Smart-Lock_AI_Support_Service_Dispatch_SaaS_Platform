"use client";

import { Timer, AlertTriangle, CircleX } from "lucide-react";
import Link from "next/link";
import type { components } from "@/types/api.generated";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
  URGENCY_STYLE,
} from "@/components/work-orders/WorkOrdersTable";

type WorkOrder = components["schemas"]["WorkOrder"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
}

type StatusGroup = "pending" | "dispatched" | "in_progress" | "done" | "cancelled";

const COLUMN_ORDER: StatusGroup[] = [
  "pending",
  "dispatched",
  "in_progress",
  "done",
  "cancelled",
];

const COLUMN_LABEL: Record<StatusGroup, string> = {
  pending: "待指派",
  dispatched: "已派工",
  in_progress: "進行中",
  done: "已完工",
  cancelled: "已取消",
};

function shortId(id: string): string {
  return id.slice(0, 8);
}

function formatRelativeRemaining(scheduled?: string | null): {
  text: string;
  color?: string;
  bold?: boolean;
  icon: "timer" | "warning" | "overdue" | "none";
} {
  if (!scheduled) return { text: "未排程", icon: "none" };
  const target = new Date(scheduled).getTime();
  const diff = target - Date.now();
  if (diff <= 0) {
    const overdueMin = Math.round(-diff / 60000);
    return {
      text: `逾時 ${overdueMin}min`,
      color: "#EF4444",
      bold: true,
      icon: "overdue",
    };
  }
  const totalSec = Math.floor(diff / 1000);
  const hh = Math.floor(totalSec / 3600);
  const mm = Math.floor((totalSec % 3600) / 60);
  const text = `剩餘 ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
  if (totalSec <= 1800) return { text, color: "#F59E0B", bold: true, icon: "warning" };
  return { text, icon: "timer" };
}

function technicianTag(technicianId: string | null | undefined): string | null {
  if (!technicianId) return null;
  return `技師 ${technicianId.slice(0, 4)}`;
}

function groupByStatus(items: WorkOrder[]): Record<StatusGroup, WorkOrder[]> {
  const acc: Record<StatusGroup, WorkOrder[]> = {
    pending: [],
    dispatched: [],
    in_progress: [],
    done: [],
    cancelled: [],
  };
  for (const item of items) {
    const group = STATUS_GROUP_MAP[item.status];
    if (!group) continue;
    acc[group].push(item);
  }
  for (const k of Object.keys(acc) as StatusGroup[]) {
    acc[k].sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""),
    );
  }
  return acc;
}

function SlaIndicator({
  sla,
}: {
  sla: ReturnType<typeof formatRelativeRemaining>;
}) {
  if (sla.icon === "none") {
    return (
      <span
        className="text-[11px] font-medium"
        style={{ color: sla.color ?? "var(--text-disabled)" }}
      >
        {sla.text}
      </span>
    );
  }
  const Icon =
    sla.icon === "overdue"
      ? CircleX
      : sla.icon === "warning"
        ? AlertTriangle
        : Timer;
  const color = sla.color ?? "var(--text-secondary)";
  return (
    <div className="flex items-center gap-1">
      <Icon className="h-[14px] w-[14px]" style={{ color }} />
      <span
        className={`text-[11px] font-medium ${sla.bold ? "font-bold" : ""}`}
        style={{ color }}
      >
        {sla.text}
      </span>
    </div>
  );
}

function CardItem({
  card,
  columnColor,
}: {
  card: WorkOrder;
  columnColor: string;
}) {
  const tech = technicianTag(card.technician_id);
  const sla = formatRelativeRemaining(card.scheduled_time);
  const urgency = URGENCY_STYLE[card.urgency];
  const districtAddr = card.district || card.address || "—";

  return (
    <Link
      href={`/work-orders/${card.id}`}
      className="flex flex-col gap-[10px] rounded-lg bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
      style={{ borderLeft: `3px solid ${columnColor}` }}
    >
      <div className="flex items-center justify-between">
        <span
          className="font-mono text-[11px] font-medium text-[var(--text-secondary)]"
          title={card.id}
        >
          {shortId(card.id)}
        </span>
        <span
          className="rounded px-2 py-[2px] text-[11px] font-semibold"
          style={{ color: urgency.color, backgroundColor: urgency.bg }}
        >
          緊急度 {urgency.label}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          {card.brand || "—"} {card.model || ""}
        </span>
        <span
          className="truncate text-[12px] text-[var(--text-secondary)]"
          title={card.address}
        >
          {districtAddr}
        </span>
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[6px]">
          <div
            className={`h-5 w-5 flex-shrink-0 rounded-full ${
              tech ? "bg-[#C4B5FD]" : "bg-[#E2E8F0]"
            }`}
          />
          {tech ? (
            <span
              className="font-mono text-[11px] font-medium text-[var(--text-primary)]"
              title={card.technician_id ?? ""}
            >
              {tech}
            </span>
          ) : (
            <span className="text-[11px] italic text-[var(--text-disabled)]">
              未指派
            </span>
          )}
        </div>
        <SlaIndicator sla={sla} />
      </div>
    </Link>
  );
}

export default function KanbanBoard({ items, loading }: Props) {
  const grouped = groupByStatus(items);

  if (loading && items.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-[var(--text-secondary)]">
        載入中…
      </div>
    );
  }

  if (!loading && items.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-[var(--text-secondary)]">
        目前沒有工單
      </div>
    );
  }

  return (
    <div className="flex h-full gap-4 p-4">
      {COLUMN_ORDER.map((group) => {
        const style = STATUS_GROUP_STYLE[group];
        const cards = grouped[group];
        return (
          <div
            key={group}
            className="flex flex-1 flex-col rounded-lg bg-[#F8FAFC]"
            style={{ borderTop: `3px solid ${style.color}` }}
          >
            <div className="flex h-12 items-center justify-between px-3">
              <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                {COLUMN_LABEL[group]}
              </span>
              <span
                className="rounded-[10px] px-2 py-[2px] text-[12px] font-semibold text-white"
                style={{ backgroundColor: style.color }}
              >
                {cards.length}
              </span>
            </div>

            <div className="flex flex-1 flex-col gap-3 overflow-auto px-3 pb-3">
              {cards.length === 0 ? (
                <span className="px-1 py-2 text-[11px] text-[var(--text-disabled)]">
                  此欄位暫無工單
                </span>
              ) : (
                cards.map((card) => (
                  <CardItem key={card.id} card={card} columnColor={style.color} />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
