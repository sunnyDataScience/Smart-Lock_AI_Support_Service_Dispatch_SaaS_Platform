"use client";

import { useMemo } from "react";
import Link from "next/link";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  URGENCY_TONE,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

interface Props {
  items: WorkOrder[];
  loading?: boolean;
  error?: string | null;
}

// Stable column keys; labels resolved per-render via i18n
const COLUMN_DEFS = [
  { key: "id" as const, width: "w-[110px]" },
  { key: "address" as const, width: "flex-1" },
  { key: "device" as const, width: "w-[160px]" },
  { key: "status" as const, width: "w-[90px]" },
  { key: "urgency" as const, width: "w-[70px]" },
  { key: "createdAt" as const, width: "w-[100px]" },
  { key: "technician" as const, width: "w-[110px]" },
];

function shortId(id: string): string {
  return id.slice(0, 8);
}

export default function RecentWorkOrders({ items, loading, error }: Props) {
  const t = useTranslations("pages.dashboard.recentWorkOrders");
  const tCols = useTranslations("pages.dashboard.recentWorkOrders.cols");
  const tGroup = useTranslations("status.workOrderGroup");
  const tUrgency = useTranslations("urgency");

  const columns = useMemo(
    () => COLUMN_DEFS.map((c) => ({ ...c, label: tCols(c.key) })),
    [tCols],
  );

  function technicianTag(technicianId: string | null | undefined): string | null {
    if (!technicianId) return null;
    return t("technicianTag", { id: technicianId.slice(0, 4) });
  }
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
          {t("title")}
        </h3>
        <Link
          href="/work-orders"
          className="text-[14px] font-medium text-[var(--primary)] hover:underline focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 rounded"
        >
          {t("viewAll")}
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
          {t("loadFailed", { error })}
        </div>
      )}

      {loading && items.length === 0 && (
        <div className="flex h-[120px] items-center justify-center text-[13px] text-[var(--text-secondary)]">
          {t("loading")}
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className="flex h-[120px] items-center justify-center text-[13px] text-[var(--text-secondary)]">
          {t("empty")}
        </div>
      )}

      {items.map((order, idx) => {
        const group = STATUS_GROUP_MAP[order.status];
        const status = STATUS_GROUP_TONE[group];
        const urgency = URGENCY_TONE[order.urgency];
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
                  {tGroup(group)}
                </span>
              </div>
              <div role="cell" className="w-[70px]">
                <span
                  className="rounded px-2 py-[2px] text-[11px] font-medium"
                  style={{ color: urgency.color, backgroundColor: urgency.bg }}
                >
                  {tUrgency(order.urgency)}
                </span>
              </div>
              <div role="cell" className="w-[100px]">
                <span className="text-[12px] text-[var(--text-tertiary)]">
                  {formatRelative(order.created_at)}
                </span>
              </div>
              <div role="cell" className="w-[110px]">
                <span className="text-[13px] text-[#18181B]">
                  {tech ?? <span className="text-[var(--text-disabled)]">{t("unassigned")}</span>}
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
              {t("showingCount", { count: items.length })}
            </span>
          </div>
        </>
      )}
    </section>
  );
}
