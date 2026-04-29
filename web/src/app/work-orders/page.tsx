"use client";

import { useCallback, useEffect, useState } from "react";
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
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const PAGE_SIZE = 20;

const filterDropdowns = [
  { label: "狀態", icon: null },
  { label: "最近 7 天", icon: Calendar },
  { label: "品牌", icon: null },
];

const viewTabs = [
  { label: "列表", icon: List, active: true, href: "/work-orders" },
  { label: "看板", icon: Columns3, active: false, href: "/work-orders/kanban" },
  { label: "地圖", icon: Map, active: false, href: "/work-orders/map" },
];

export default function WorkOrdersPage() {
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(async (afterCursor: string | null, append: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: PAGE_SIZE };
      if (afterCursor) query.cursor = afterCursor;
      const res = await api.get<WorkOrderPage>("/api/v1/work-orders", { query });
      const newItems = res.items ?? [];
      setItems((prev) => (append ? [...prev, ...newItems] : newItems));
      setCursor(res.next_cursor ?? null);
      setHasMore(!!res.has_more);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPage(null, false);
  }, [fetchPage]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 工單管理 &gt; 工單列表
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">工單管理</h1>
            <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">共</span>
              <span className="text-[13px] font-bold text-[var(--text-primary)]">
                {loading && items.length === 0 ? "—" : items.length}
              </span>
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                {hasMore ? "+ 筆工單" : "筆工單"}
              </span>
            </div>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          {/* Search disabled */}
          <div className="flex h-9 w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              placeholder="搜尋功能即將推出"
              disabled
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)] cursor-not-allowed"
            />
          </div>

          {/* Filter Dropdowns disabled */}
          {filterDropdowns.map((dd) => (
            <button
              key={dd.label}
              disabled
              title="即將推出"
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
                key={tab.label}
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
        <main className="flex flex-1 flex-col gap-4 overflow-auto bg-[var(--bg-page)] px-8 py-5">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入工單失敗：{error}
            </div>
          )}

          <WorkOrdersTable items={items} loading={loading} />

          {hasMore && items.length > 0 && (
            <div className="flex justify-center">
              <button
                disabled={loading}
                onClick={() => fetchPage(cursor, true)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
