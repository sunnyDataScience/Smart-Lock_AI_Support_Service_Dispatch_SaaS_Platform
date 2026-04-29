"use client";

import { ArrowUpDown } from "lucide-react";
import Link from "next/link";
import type { components } from "@/types/api.generated";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
} from "@/components/work-orders/WorkOrdersTable";

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

function technicianTag(technicianId: string | null | undefined): string | null {
  if (!technicianId) return null;
  return `技師 ${technicianId.slice(0, 4)}`;
}

function formatRemainingShort(scheduled?: string | null): {
  text: string;
  color?: string;
  bold?: boolean;
} {
  if (!scheduled) return { text: "未排程", color: "var(--text-disabled)" };
  const target = new Date(scheduled).getTime();
  const diff = target - Date.now();
  if (diff <= 0) {
    const overdueMin = Math.round(-diff / 60000);
    return { text: `逾時 ${overdueMin}min`, color: "#EF4444", bold: true };
  }
  const totalSec = Math.floor(diff / 1000);
  const hh = Math.floor(totalSec / 3600);
  const mm = Math.floor((totalSec % 3600) / 60);
  const text = `剩餘 ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
  if (totalSec <= 1800) return { text, color: "#F59E0B", bold: true };
  return { text };
}

export default function MapWorkOrderPanel({
  items,
  loading,
  selectedId,
  onSelect,
}: Props) {
  return (
    <div className="flex w-[400px] flex-shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-[14px]">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            工單列表
          </span>
          <span className="flex h-[22px] items-center justify-center rounded-full bg-[var(--primary)] px-2 text-[11px] font-semibold text-white">
            {loading && items.length === 0 ? "—" : items.length}
          </span>
        </div>
        <button
          disabled
          title="即將推出"
          className="flex cursor-not-allowed items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-2 py-1 opacity-60"
        >
          <ArrowUpDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
          <span className="text-[12px] text-[var(--text-disabled)]">
            SLA 排序
          </span>
        </button>
      </div>

      <div className="flex flex-1 flex-col overflow-auto">
        {loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            載入中…
          </div>
        )}
        {!loading && items.length === 0 && (
          <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
            目前沒有工單
          </div>
        )}

        {items.map((item) => {
          const isActive = item.id === selectedId;
          const group = STATUS_GROUP_MAP[item.status];
          const style = STATUS_GROUP_STYLE[group];
          const remaining = formatRemainingShort(item.scheduled_time);
          const tech = technicianTag(item.technician_id);
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
                  style={{ color: style.color, backgroundColor: style.bg }}
                >
                  {style.label}
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
                  {tech ?? "未指派"}
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
