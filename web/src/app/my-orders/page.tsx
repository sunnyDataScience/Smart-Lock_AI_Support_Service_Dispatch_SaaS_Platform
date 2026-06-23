"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, ClipboardList, RefreshCw } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import StatusBadge from "@/components/tech/StatusBadge";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, tenantPath } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];

type TabKey = "active" | "pending" | "history";

const TAB_STATUSES: Record<TabKey, WorkOrderStatus[]> = {
  active: [
    "accepted",
    "scheduled",
    "assigned",
    "en_route",
    "arrived",
    "in_progress",
  ],
  pending: ["completed", "billed"],
  history: ["paid", "closed", "cancelled"],
};

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function MyOrdersPage() {
  const t = useTranslations("techPortal.myOrders");
  const tTabs = useTranslations("techPortal.myOrders.tabs");
  const tEmpty = useTranslations("techPortal.myOrders.empty");
  const tCommon = useTranslations("techPortal.common");
  const [tab, setTab] = useState<TabKey>("active");
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tabs = useMemo(
    () => [
      { value: "active" as TabKey, label: tTabs("active"), statuses: TAB_STATUSES.active },
      { value: "pending" as TabKey, label: tTabs("pending"), statuses: TAB_STATUSES.pending },
      { value: "history" as TabKey, label: tTabs("history"), statuses: TAB_STATUSES.history },
    ],
    [tTabs],
  );

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // work_orders.technician_id = technicians.id（非 JWT sub 的 user_id），先取 profile
      const profile = await api.get<TechnicianEnvelope>("/api/v1/technicians/me");
      const techId = profile.data?.id;
      if (!techId) {
        setError(t("errorNoSession"));
        return;
      }
      const res = await api.get<WorkOrderPage>(tenantPath("/work-orders"), {
        query: { technician_id: techId, limit: 50 },
      });
      setItems(res.items ?? []);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const tabStatuses = TAB_STATUSES[tab];
  const visible = items.filter((x) => tabStatuses.includes(x.status));
  const counts = (Object.keys(TAB_STATUSES) as TabKey[]).reduce<Record<TabKey, number>>(
    (acc, key) => {
      acc[key] = items.filter((x) => TAB_STATUSES[key].includes(x.status)).length;
      return acc;
    },
    { active: 0, pending: 0, history: 0 },
  );

  return (
    <TechShell wide>
      {/* page_header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
        <h1 className="text-[18px] font-semibold text-[var(--text-primary)]">{t("title")}</h1>
        <button
          type="button"
          onClick={fetchList}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title={t("refreshTitle")}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* tab_bar */}
      <div className="sticky top-[57px] z-10 grid grid-cols-3 border-b border-[var(--border)] bg-[var(--bg-surface)]">
        {tabs.map((tabItem) => (
          <button
            key={tabItem.value}
            type="button"
            onClick={() => setTab(tabItem.value)}
            className={`relative flex h-12 items-center justify-center gap-1 text-[14px] font-medium ${
              tab === tabItem.value
                ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                : "text-[var(--text-secondary)]"
            }`}
          >
            {tabItem.label}
            {counts[tabItem.value] > 0 && (
              <span
                className={`min-w-[18px] rounded-full px-[6px] py-[1px] text-[10px] font-bold ${
                  tab === tabItem.value
                    ? "bg-[var(--primary)] text-white"
                    : "bg-[var(--border)] text-[var(--text-secondary)]"
                }`}
              >
                {counts[tabItem.value]}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 px-4 py-4 md:grid-cols-2 xl:grid-cols-3">
        {loading && items.length === 0 ? (
          <div className="col-span-full flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            {tCommon("loading")}
          </div>
        ) : visible.length === 0 ? (
          <div className="col-span-full flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
            <ClipboardList className="h-10 w-10 text-[var(--text-disabled)]" />
            <p className="text-[14px]">{tEmpty(tab)}</p>
            {tab === "active" && (
              <Link
                href="/pool"
                className="mt-2 rounded-md bg-[var(--primary)] px-3 py-2 text-[12px] font-semibold text-white"
              >
                {t("goToPool")}
              </Link>
            )}
          </div>
        ) : (
          visible.map((wo) => (
            <Link
              key={wo.id}
              href={`/my-orders/${wo.id}`}
              className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm transition hover:bg-[var(--bg-page)]"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-[11px] text-[var(--text-disabled)]">
                  #{wo.id.slice(0, 8)}
                </span>
                <div className="flex items-center gap-1">
                  <UrgencyBadge urgency={wo.urgency} />
                  <StatusBadge status={wo.status} />
                </div>
              </div>
              <h3 className="text-[15px] font-semibold text-[var(--text-primary)] line-clamp-2">
                {wo.address}
              </h3>
              <div className="flex items-center gap-2 text-[12px] text-[var(--text-secondary)]">
                <span className="rounded bg-[var(--surface-strong)] px-2 py-[2px]">
                  {wo.brand} {wo.model}
                </span>
                <span>·</span>
                <span>{wo.district}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-[var(--text-disabled)]">
                <span>{formatRelative(wo.updated_at)}</span>
                <ChevronRight className="h-4 w-4" />
              </div>
            </Link>
          ))
        )}
      </div>
    </TechShell>
  );
}
