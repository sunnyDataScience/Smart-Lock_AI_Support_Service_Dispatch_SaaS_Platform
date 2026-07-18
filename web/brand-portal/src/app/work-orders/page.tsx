"use client";

import {
  Search,
  ChevronDown,
  Calendar,
  List,
  Columns3,
  Map,
  Plus,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrdersTable from "@/components/work-orders/WorkOrdersTable";
import CreateWorkOrderModal from "@/components/work-orders/CreateWorkOrderModal";
import { tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { useMemo, useState } from "react";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

const PAGE_SIZE = 20;

/** 保留既有 page error 格式（errorCode (status)：message）— hook 預設只回 message */
function formatWorkOrderError(e: unknown): string {
  return friendlyError(e);
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

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [periodFilter, setPeriodFilter] = useState<string>(""); // 7/30/all
  const [keyword, setKeyword] = useState<string>("");

  const filterDropdowns = useMemo(
    () => FILTER_DROPDOWN_DEFS.map((d) => ({ ...d, label: tFilters(d.key) })),
    [tFilters],
  );
  const viewTabs = useMemo(
    () => VIEW_TAB_DEFS.map((d) => ({ ...d, label: tViews(d.key) })),
    [tViews],
  );

  const queryParams = useMemo(() => {
    const p = new URLSearchParams();
    if (statusFilter) p.set("status", statusFilter);
    if (brandFilter) p.set("brand", brandFilter);
    if (keyword.trim()) p.set("keyword", keyword.trim());
    if (periodFilter) {
      const days = parseInt(periodFilter, 10);
      if (!Number.isNaN(days)) {
        const since = new Date(Date.now() - days * 24 * 3600 * 1000);
        p.set("created_after", since.toISOString());
      }
    }
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  }, [statusFilter, brandFilter, periodFilter, keyword]);

  // P3：全 cutover 至 tenant-scoped v2 路徑（tenantPath 同步解析 tenantId）。
  const [createOpen, setCreateOpen] = useState(false);

  const { items, cursor, hasMore, loading, error, loadMore, refresh } = usePaginatedFetch<WorkOrder>({
    path: `${tenantPath("/work-orders")}${queryParams}`,
    pageSize: PAGE_SIZE,
    formatError: formatWorkOrderError,
  });

  // 從 items 抽 distinct brands
  const brandOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((wo: any) => {
      if (wo.brand) set.add(wo.brand);
    });
    return Array.from(set).sort();
  }, [items]);

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
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">{t("title")}</h1>
            <div className="flex items-center gap-[6px] rounded-md bg-[var(--bg-page)] px-3 py-[6px]">
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

        {/* Toolbar — UAT W6-4：加 flex-wrap，390px 窄幅時控制項換行不撐出水平溢出 */}
        <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          <div className="flex h-9 w-full max-w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 sm:w-[280px]">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="flex-1 bg-transparent text-[13px] outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("status")}</option>
            <option value="dispatched">{tFilters("statusOptions.dispatched")}</option>
            <option value="completed">{tFilters("statusOptions.completed")}</option>
            <option value="refunded">{tFilters("statusOptions.refunded")}</option>
            <option value="disputed">{tFilters("statusOptions.disputed")}</option>
          </select>

          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("last7Days")}</option>
            <option value="7">{tFilters("periodOptions.7")}</option>
            <option value="30">{tFilters("periodOptions.30")}</option>
            <option value="90">{tFilters("periodOptions.90")}</option>
          </select>

          <select
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("brand")}</option>
            {brandOptions.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>

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

          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="flex h-9 items-center gap-[6px] rounded-md bg-[var(--primary)] px-4 hover:opacity-90"
          >
            <Plus className="h-4 w-4 text-white" />
            <span className="text-[13px] font-medium text-white">{t("createOrder")}</span>
          </button>
        </div>

        {/* Table Area */}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex flex-1 min-h-0 flex-col gap-4 overflow-auto bg-[var(--bg-page)] px-8 py-5"
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

      <CreateWorkOrderModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={() => refresh()}
      />
    </div>
  );
}
