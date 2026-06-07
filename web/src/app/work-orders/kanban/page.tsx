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
import KanbanBoard from "@/components/work-orders/KanbanBoard";
import CreateWorkOrderModal from "@/components/work-orders/CreateWorkOrderModal";
import { ApiError, api, tenantPath } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const PAGE_SIZE = 100;

const viewTabs = [
  { label: "列表", icon: List, active: false, href: "/work-orders" },
  { label: "看板", icon: Columns3, active: true, href: "/work-orders/kanban" },
  { label: "地圖", icon: Map, active: false, href: "/work-orders/map" },
];

export default function WorkOrdersKanbanPage() {
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [periodFilter, setPeriodFilter] = useState<string>("");
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");

  const queryObj = useMemo(() => {
    const q: Record<string, string | number> = { limit: PAGE_SIZE };
    if (statusFilter) q.status = statusFilter;
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

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 工單管理 &gt; 派工板
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">工單管理</h1>
            <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                共
              </span>
              <span className="text-[13px] font-bold text-[var(--text-primary)]">
                {loading && items.length === 0 ? "—" : items.length}
              </span>
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                筆工單
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
              placeholder="搜尋客戶 / 地址 / 電話"
              className="flex-1 bg-transparent text-[13px] outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">狀態</option>
            <option value="dispatched">已派工</option>
            <option value="completed">已完工</option>
            <option value="refunded">已退款</option>
            <option value="disputed">爭議中</option>
          </select>

          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">最近 7 天</option>
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
            <option value="90">最近 90 天</option>
          </select>

          <select
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">品牌</option>
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
                key={tab.label}
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
            <span className="text-[13px] font-medium text-white">新增工單</span>
          </button>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            載入工單失敗：{error}
          </div>
        )}

        <main className="flex-1 overflow-auto">
          <KanbanBoard items={items} loading={loading} />
        </main>
      </div>

      <CreateWorkOrderModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={() => fetchOrders()}
      />
    </div>
  );
}
