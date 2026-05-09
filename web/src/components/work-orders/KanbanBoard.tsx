"use client";

import { useMemo } from "react";
import { Timer, AlertTriangle, CircleX } from "lucide-react";
import Link from "next/link";
import type { components } from "@/types/api.generated";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  URGENCY_TONE,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type WorkOrder = components["schemas"]["WorkOrder"];
type Urgency = components["schemas"]["Urgency"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
}

const COLUMN_ORDER: StatusGroup[] = [
  "pending",
  "dispatched",
  "in_progress",
  "done",
  "cancelled",
];

function shortId(id: string): string {
  return id.slice(0, 8);
}

interface SlaInfo {
  text: string;
  color?: string;
  bold?: boolean;
  icon: "timer" | "warning" | "overdue" | "none";
}

function computeSla(
  scheduled: string | null | undefined,
  t: (key: string, params?: Record<string, string | number>) => string,
): SlaInfo {
  if (!scheduled) return { text: t("unscheduled"), icon: "none" };
  const target = new Date(scheduled).getTime();
  const diff = target - Date.now();
  if (diff <= 0) {
    const overdueMin = Math.round(-diff / 60000);
    return {
      text: t("overdue", { minutes: overdueMin }),
      color: "#EF4444",
      bold: true,
      icon: "overdue",
    };
  }
  const totalSec = Math.floor(diff / 1000);
  const hh = Math.floor(totalSec / 3600);
  const mm = Math.floor((totalSec % 3600) / 60);
  const text = t("remaining", {
    hh: String(hh).padStart(2, "0"),
    mm: String(mm).padStart(2, "0"),
  });
  if (totalSec <= 1800) return { text, color: "#F59E0B", bold: true, icon: "warning" };
  return { text, icon: "timer" };
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

function SlaIndicator({ sla }: { sla: SlaInfo }) {
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
  urgencyLabels,
  unassignedLabel,
  techLabel,
  sla,
}: {
  card: WorkOrder;
  columnColor: string;
  urgencyLabels: Record<Urgency, string>;
  unassignedLabel: string;
  techLabel: (id: string) => string;
  sla: SlaInfo;
}) {
  const tech = card.technician_id ? techLabel(card.technician_id.slice(0, 4)) : null;
  const urgencyTone = URGENCY_TONE[card.urgency];
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
          style={{ color: urgencyTone.color, backgroundColor: urgencyTone.bg }}
        >
          {urgencyLabels[card.urgency]}
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
              {unassignedLabel}
            </span>
          )}
        </div>
        <SlaIndicator sla={sla} />
      </div>
    </Link>
  );
}

export default function KanbanBoard({ items, loading }: Props) {
  const t = useTranslations("components.workOrders.kanban");
  const tColumn = useTranslations("components.workOrders.kanban.column");
  const tUrgency = useTranslations("urgency");

  const columnLabels: Record<StatusGroup, string> = useMemo(
    () => ({
      pending: tColumn("pending"),
      dispatched: tColumn("dispatched"),
      in_progress: tColumn("in_progress"),
      done: tColumn("done"),
      cancelled: tColumn("cancelled"),
    }),
    [tColumn],
  );

  const urgencyLabels: Record<Urgency, string> = useMemo(
    () => ({
      low: t("urgency", { label: tUrgency("low") }),
      medium: t("urgency", { label: tUrgency("medium") }),
      high: t("urgency", { label: tUrgency("high") }),
    }),
    [t, tUrgency],
  );

  const grouped = groupByStatus(items);

  if (loading && items.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-[var(--text-secondary)]">
        {t("loading")}
      </div>
    );
  }

  if (!loading && items.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-[var(--text-secondary)]">
        {t("empty")}
      </div>
    );
  }

  const techLabel = (id: string) => t("techTag", { id });
  const unassignedLabel = t("unassignedItalic");

  return (
    <div className="flex h-full gap-4 p-4">
      {COLUMN_ORDER.map((group) => {
        const tone = STATUS_GROUP_TONE[group];
        const cards = grouped[group];
        return (
          <div
            key={group}
            className="flex flex-1 flex-col rounded-lg bg-[#F8FAFC]"
            style={{ borderTop: `3px solid ${tone.color}` }}
          >
            <div className="flex h-12 items-center justify-between px-3">
              <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                {columnLabels[group]}
              </span>
              <span
                className="rounded-[10px] px-2 py-[2px] text-[12px] font-semibold text-white"
                style={{ backgroundColor: tone.color }}
              >
                {cards.length}
              </span>
            </div>

            <div className="flex flex-1 flex-col gap-3 overflow-auto px-3 pb-3">
              {cards.length === 0 ? (
                <span className="px-1 py-2 text-[11px] text-[var(--text-disabled)]">
                  {t("columnEmpty")}
                </span>
              ) : (
                cards.map((card) => (
                  <CardItem
                    key={card.id}
                    card={card}
                    columnColor={tone.color}
                    urgencyLabels={urgencyLabels}
                    unassignedLabel={unassignedLabel}
                    techLabel={techLabel}
                    sla={computeSla(card.scheduled_time, t)}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
