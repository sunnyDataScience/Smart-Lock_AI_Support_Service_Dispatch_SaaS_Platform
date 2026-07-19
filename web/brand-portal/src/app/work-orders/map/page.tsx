"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Search,
  List,
  Columns3,
  Map,
  Plus,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import MapWorkOrderPanel from "@/components/work-orders/MapWorkOrderPanel";
import MapView from "@/components/work-orders/MapView";
import CreateWorkOrderModal from "@/components/work-orders/CreateWorkOrderModal";
import {
  STATUS_GROUP_VALUES,
  rawStatusesOfGroup,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const PAGE_SIZE = 100;

// key 對應 pages.workOrders.views.*（UAT R3-7：option/tab 文字接 i18n）
const VIEW_TAB_DEFS = [
  { key: "list" as const, icon: List, active: false, href: "/work-orders" },
  { key: "kanban" as const, icon: Columns3, active: false, href: "/work-orders/kanban" },
  { key: "map" as const, icon: Map, active: true, href: "/work-orders/map" },
];

export default function WorkOrdersMapPage() {
  const t = useTranslations("pages.workOrders");
  const tFilters = useTranslations("pages.workOrders.filters");
  const tViews = useTranslations("pages.workOrders.views");
  const tGroup = useTranslations("status.workOrderGroup");

  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const [statusFilter, setStatusFilter] = useState<string>("");
  // UAT R3（P3）：期間預設「最近 7 天」要真的帶條件（label 與行為一致）
  const [periodFilter, setPeriodFilter] = useState<string>("7");
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");
  const [slaSort, setSlaSort] = useState(false);

  const viewTabs = useMemo(
    () => VIEW_TAB_DEFS.map((d) => ({ ...d, label: tViews(d.key) })),
    [tViews],
  );

  const queryObj = useMemo(() => {
    const q: Record<string, string | number | string[]> = { limit: PAGE_SIZE };
    // UAT R3-7：群組值展開成多個原始 status（api.ts buildUrl 陣列展開）
    if (statusFilter) q.status = rawStatusesOfGroup(statusFilter as StatusGroup);
    if (brandFilter) q.brand = brandFilter;
    if (keyword.trim()) q.keyword = keyword.trim();
    if (periodFilter) {
      const days = parseInt(periodFilter, 10);
      if (!Number.isNaN(days)) {
        q.created_after = new Date(
          Date.now() - days * 24 * 3600 * 1000,
        ).toISOString();
      }
    }
    return q;
  }, [statusFilter, periodFilter, brandFilter, keyword]);

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WorkOrderPage>(tenantPath("/work-orders"), {
        query: queryObj,
      });
      const newItems: WorkOrder[] = res.items ?? [];
      setItems(newItems);
      if (newItems.length > 0 && !selectedId) {
        setSelectedId(newItems[0].id);
      }
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, periodFilter, brandFilter, keyword]);

  const brandOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((wo: any) => {
      if (wo.brand) set.add(wo.brand);
    });
    return Array.from(set).sort();
  }, [items]);

  const selectedItem = items.find((it) => it.id === selectedId) ?? null;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {t("breadcrumbMap")}
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">{t("title")}</h1>
            <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                {t("totalLabelPrefix")}
              </span>
              <span className="text-[13px] font-bold text-[var(--text-primary)]">
                {loading && items.length === 0 ? "—" : items.length}
              </span>
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                {t("totalOrders")}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          <div className="flex h-9 w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("searchKeywordPlaceholder")}
              className="flex-1 bg-transparent text-[13px] outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("status")}</option>
            {STATUS_GROUP_VALUES.map((g) => (
              <option key={g} value={g}>
                {tGroup(g)}
              </option>
            ))}
          </select>

          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="7">{tFilters("periodOptions.7")}</option>
            <option value="30">{tFilters("periodOptions.30")}</option>
            <option value="90">{tFilters("periodOptions.90")}</option>
            <option value="">{tFilters("periodOptions.all")}</option>
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
                <span
                  className={`text-[13px] ${tab.active ? "font-medium" : ""}`}
                >
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

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {t("loadFailed", { error })}
          </div>
        )}

        <div className="flex flex-1 overflow-hidden">
          <MapWorkOrderPanel
            items={items}
            loading={loading}
            selectedId={selectedId}
            onSelect={setSelectedId}
            slaSort={slaSort}
            onToggleSlaSort={() => setSlaSort((v) => !v)}
          />
          <MapView
            items={items}
            selectedItem={selectedItem}
            onClose={() => setSelectedId(null)}
          />
        </div>
      </div>

      <CreateWorkOrderModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={() => fetchOrders()}
      />
    </div>
  );
}
