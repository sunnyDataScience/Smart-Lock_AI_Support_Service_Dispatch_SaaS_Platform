"use client";

import { useEffect, useState } from "react";
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
import KanbanBoard from "@/components/work-orders/KanbanBoard";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const PAGE_SIZE = 100;

const filterDropdowns = [
  { label: "狀態", icon: null },
  { label: "最近 7 天", icon: Calendar },
  { label: "品牌", icon: null },
];

const viewTabs = [
  { label: "列表", icon: List, active: false, href: "/work-orders" },
  { label: "看板", icon: Columns3, active: true, href: "/work-orders/kanban" },
  { label: "地圖", icon: Map, active: false, href: "/work-orders/map" },
];

export default function WorkOrdersKanbanPage() {
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WorkOrderPage>("/api/v1/work-orders", {
        query: { limit: PAGE_SIZE },
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
  }, []);

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
          <div className="flex h-9 w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              disabled
              placeholder="搜尋功能即將推出"
              className="flex-1 cursor-not-allowed bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          {filterDropdowns.map((dd) => (
            <button
              key={dd.label}
              disabled
              title="即將推出"
              className="flex h-9 cursor-not-allowed items-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60"
            >
              {dd.icon && (
                <dd.icon className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
              )}
              <span className="text-[13px] text-[var(--text-disabled)]">
                {dd.label}
              </span>
              <ChevronDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
            </button>
          ))}

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
            disabled
            title="即將推出"
            className="flex h-9 cursor-not-allowed items-center gap-[6px] rounded-md bg-[#CBD5E1] px-4 opacity-70"
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
    </div>
  );
}
