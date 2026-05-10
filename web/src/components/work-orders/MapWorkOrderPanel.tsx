"use client";

import { useMemo } from "react";
import { ArrowUpDown } from "lucide-react";
import Link from "next/link";
import type { components } from "@/types/api.generated";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type WorkOrder = components["schemas"]["WorkOrder"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function shortId(id: string): string {
  return id.slice(0, 8);
}

interface Remaining {
  text: string;
  color?: string;
  bold?: boolean;
}

function computeRemaining(
  scheduled: string | null | undefined,
  t: (key: string, params?: Record<string, string | number>) => string,
): Remaining {
  if (!scheduled) return { text: t("unscheduled"), color: "var(--text-disabled)" };
  const target = new Date(scheduled).getTime();
  const diff = target - Date.now();
  if (diff <= 0) {
    const overdueMin = Math.round(-diff / 60000);
    return { text: t("overdue", { minutes: overdueMin }), color: "#EF4444", bold: true };
  }
  const totalSec = Math.floor(diff / 1000);
  const hh = Math.floor(totalSec / 3600);
  const mm = Math.floor((totalSec % 3600) / 60);
  const text = t("remaining", {
    hh: String(hh).padStart(2, "0"),
    mm: String(mm).padStart(2, "0"),
  });
  if (totalSec <= 1800) return { text, color: "#F59E0B", bold: true };
  return { text };
}

export default function MapWorkOrderPanel({
  items,
  loading,
  selectedId,
  onSelect,
}: Props) {
  const t = useTranslations("components.workOrders.mapPanel");
  const tGroup = useTranslations("status.workOrderGroup");

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

  return (
    <div className="flex w-[400px] flex-shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-[14px]">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
          <span className="flex h-[22px] items-center justify-center rounded-full bg-[var(--primary)] px-2 text-[11px] font-semibold text-white">
            {loading && items.length === 0 ? "—" : items.length}
          </span>
        </div>
        <button
          disabled
          title={t("comingSoon")}
          className="flex cursor-not-allowed items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-2 py-1 opacity-60"
        >
          <ArrowUpDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
          <span className="text-[12px] text-[var(--text-disabled)]">
            {t("slaSort")}
          </span>
        </button>
      </div>

      <div className="flex flex-1 flex-col overflow-auto">
        {loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            {t("loading")}
          </div>
        )}
        {!loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            {t("empty")}
          </div>
        )}

        {items.map((item) => {
          const isActive = item.id === selectedId;
          const group = STATUS_GROUP_MAP[item.status];
          const tone = STATUS_GROUP_TONE[group];
          const remaining = computeRemaining(item.scheduled_time, t);
          const tech = item.technician_id
            ? t("techTag", { id: item.technician_id.slice(0, 4) })
            : null;
          const districtAddr = item.district || item.address || "—";

          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={`flex flex-col gap-2 px-4 py-3 text-left transition-colors ${
                isActive
                  ? "border-b border-[var(--primary)] border-l-[3px] bg-[#EFF6FF]"
                  : "border-b border-[var(--border)] hover:bg-[var(--bg-page)]"
              }`}
            >
              <div className="flex items-center justify-between">
                <Link
                  href={`/work-orders/${item.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="font-mono text-[12px] font-medium text-[var(--primary)] hover:underline"
                  title={item.id}
                >
                  {shortId(item.id)}
                </Link>
                <span
                  className="rounded-full px-2 text-[11px] font-medium leading-5"
                  style={{ color: tone.color, backgroundColor: tone.bg }}
                >
                  {groupLabels[group]}
                </span>
              </div>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {item.brand || "—"} {item.model || ""}
              </span>
              <span
                className="truncate text-[12px] text-[var(--text-secondary)]"
                title={item.address}
              >
                {districtAddr}
              </span>
              <div className="flex items-center justify-between">
                <span className="text-[12px] text-[var(--text-secondary)]">
                  {tech ?? t("unassigned")}
                </span>
                <span
                  className={`text-[12px] ${remaining.bold ? "font-bold" : ""}`}
                  style={{ color: remaining.color ?? "var(--text-secondary)" }}
                >
                  {remaining.text}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
