"use client";

import Link from "next/link";
import { MapPin, Navigation, ChevronRight, CalendarClock } from "lucide-react";
import StatusBadge from "@/components/tech/StatusBadge";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

const ACTIVE_STATUSES: WorkOrderStatus[] = [
  "accepted",
  "scheduled",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
];

interface Props {
  orders: WorkOrder[];
  loading: boolean;
}

/**
 * TodayScheduleSummary — 決策屏「今日行程」：進行中工單數 + 釘住當前/下一張工單卡。
 * 資料來自父層的我的工單列表（GET /work-orders?technician_id），前端過濾 active 狀態。
 */
export default function TodayScheduleSummary({ orders, loading }: Props) {
  const t = useTranslations("techPortal.home.today");

  const active = orders
    .filter((o) => ACTIVE_STATUSES.includes(o.status))
    .sort((a, b) => {
      // 有預約時間者優先，依時間升序；其餘依建立時間
      const at = a.scheduled_time ?? a.created_at ?? "";
      const bt = b.scheduled_time ?? b.created_at ?? "";
      return at.localeCompare(bt);
    });

  const inProgress = active.filter((o) => o.status === "in_progress").length;
  const current = active[0];

  return (
    <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-[var(--primary)]" />
          <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </h2>
        </div>
        <span className="text-[12px] text-[var(--text-secondary)]">
          {t("summary", { active: active.length, inProgress })}
        </span>
      </div>

      {loading && orders.length === 0 ? (
        <div className="py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("loading")}
        </div>
      ) : !current ? (
        <div className="flex flex-col items-center gap-1 py-6 text-center">
          <MapPin className="h-8 w-8 text-[var(--text-disabled)]" />
          <p className="text-[13px] text-[var(--text-secondary)]">{t("empty")}</p>
          <Link
            href="/pool"
            className="mt-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-[12px] font-semibold text-white"
          >
            {t("goPool")}
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <Link
            href={`/my-orders/${current.id}`}
            className="block rounded-lg border border-[var(--border)] p-3 transition hover:bg-[var(--bg-page)]"
          >
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[11px] font-medium text-[var(--primary)]">
                {t("currentTag")}
              </span>
              <StatusBadge status={current.status} />
            </div>
            <h3 className="text-[14px] font-semibold text-[var(--text-primary)] line-clamp-1">
              {current.address}
            </h3>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-[var(--text-secondary)]">
              <span className="rounded bg-[#F1F5F9] px-2 py-[2px]">
                {current.brand} {current.model}
              </span>
              <span>{current.district}</span>
            </div>
          </Link>

          <div className="flex items-center gap-2">
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(current.address)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--primary)] py-2.5 text-[13px] font-semibold text-white"
            >
              <Navigation className="h-4 w-4" />
              {t("navigate")}
            </a>
            <Link
              href="/my-orders"
              className="flex items-center justify-center gap-1 rounded-lg border border-[var(--border)] px-3 py-2.5 text-[13px] font-medium text-[var(--text-secondary)]"
            >
              {t("viewAll")}
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
