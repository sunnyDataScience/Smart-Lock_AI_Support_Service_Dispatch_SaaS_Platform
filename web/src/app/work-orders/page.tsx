"use client";

import {
  Search,
  ChevronDown,
  Calendar,
  List,
  Columns3,
  Map,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrdersTable from "@/components/work-orders/WorkOrdersTable";
import { ApiError, tenantPath } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { useMemo } from "react";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

const PAGE_SIZE = 20;

/** 保留既有 page error 格式（errorCode (status)：message）— hook 預設只回 message */
function formatWorkOrderError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

// Filter / view tabs use stable keys; labels resolved per-render via i18n
const FILTER_DROPDOWN_DEFS = [
  { key: "status" as const, icon: null },
  { key: "last7Days" as const, icon: Calendar },
  { key: "brand" as const, icon: null },
];

const VIEW_TAB_DEFS = [
  { key: "list" as const, icon: List, active: true, href: "/work-orders" },
  { key: "kanban" as const, icon: Columns3, active: false, href: "/work-orders/kanban" },
  { key: "map" as const, icon: Map, active: false, href: "/work-orders/map" },
];

export default function WorkOrdersPage() {
  const t = useTranslations("pages.workOrders");
  const tFilters = useTranslations("pages.workOrders.filters");
  const tViews = useTranslations("pages.workOrders.views");

  const filterDropdowns = useMemo(
    () => FILTER_DROPDOWN_DEFS.map((d) => ({ ...d, label: tFilters(d.key) })),
    [tFilters],
  );
  const viewTabs = useMemo(
    () => VIEW_TAB_DEFS.map((d) => ({ ...d, label: tViews(d.key) })),
    [tViews],
  );

  // P3：全 cutover 至 tenant-scoped v2 路徑（tenantPath 同步解析 tenantId）。
  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<WorkOrder>({
    path: tenantPath("/work-orders"),
    pageSize: PAGE_SIZE,
    formatError: formatWorkOrderError,
  });

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Page Header — mobile 加 pl-14 給 floating Hamburger 留空間 */}
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] py-4 pl-14 pr-4 md:px-8">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {t("breadcrumb")}
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">{t("title")}</h1>
            <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">{t("totalLabelPrefix")}</span>
              <span className="text-[13px] font-bold text-[var(--text-primary)]">
                {loading && items.length === 0 ? "—" : items.length}
              </span>
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                {hasMore ? t("totalOrdersMore") : t("totalOrders")}
              </span>
            </div>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          {/* Search disabled */}
          <div className="flex h-9 w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              placeholder={t("searchPlaceholder")}
              disabled
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)] cursor-not-allowed"
            />
          </div>

          {/* Filter Dropdowns disabled */}
          {filterDropdowns.map((dd) => (
            <button
              key={dd.key}
              disabled
              title={t("comingSoonTitle")}
              className="flex h-9 items-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60 cursor-not-allowed"
            >
              {dd.icon && (
                <dd.icon className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              )}
              <span className="text-[13px] text-[var(--text-primary)]">{dd.label}</span>
              <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
            </button>
          ))}

          <div className="flex-1" />

          {/* View Toggle */}
          <div className="flex h-9 items-center rounded-md border border-[var(--border)] bg-[var(--bg-surface)]">
            {viewTabs.map((tab) => (
              <Link
                key={tab.key}
                href={tab.href}
                className={`flex h-9 items-center justify-center gap-[6px] rounded-md px-3 ${
                  tab.active
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                <tab.icon className="h-4 w-4" />
                <span className={`text-[13px] ${tab.active ? "font-medium" : ""}`}>
                  {tab.label}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Table Area */}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex flex-1 flex-col gap-4 overflow-auto bg-[var(--bg-page)] px-8 py-5"
        >
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {t("loadFailed", { error })}
            </div>
          )}

          <WorkOrdersTable items={items} loading={loading} />

          {hasMore && items.length > 0 && (
            <div className="flex justify-center">
              <button
                disabled={loading || !cursor}
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? t("loadingMore") : t("loadMore")}
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
