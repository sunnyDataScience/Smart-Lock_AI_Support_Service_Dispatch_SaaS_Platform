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
import KanbanBoard from "@/components/work-orders/KanbanBoard";

const filterDropdowns = [
  { label: "狀態", icon: null },
  { label: "最近7天", icon: Calendar },
  { label: "品牌", icon: null },
];

const viewTabs = [
  { label: "列表", icon: List, active: false, href: "/work-orders" },
  { label: "看板", icon: Columns3, active: true, href: "/work-orders/kanban" },
  { label: "地圖", icon: Map, active: false, href: "/work-orders/map" },
];

export default function WorkOrdersKanbanPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex flex-col gap-1 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 工單管理 &gt; 派工板
          </span>
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-bold text-[#0F172A]">工單管理</h1>
            <div className="flex items-center gap-1">
              <span className="text-[14px] text-[var(--text-secondary)]">
                共 847 筆工單
              </span>
              <span className="text-[14px] text-[var(--text-secondary)]">
                {" | "}
              </span>
              <span className="text-[14px] text-[var(--text-secondary)]">
                待指派 23
              </span>
              <span className="text-[14px] text-[var(--text-secondary)]">
                {" | "}
              </span>
              <span className="text-[14px] font-semibold text-[#EF4444]">
                逾時 5
              </span>
            </div>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          <div className="flex h-9 w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="搜尋工單編號、客戶姓名、地址..."
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          {filterDropdowns.map((dd) => (
            <button
              key={dd.label}
              className="flex h-9 items-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3"
            >
              {dd.icon && (
                <dd.icon className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              )}
              <span className="text-[13px] text-[var(--text-primary)]">
                {dd.label}
              </span>
              <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
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

          <button className="flex h-9 items-center gap-[6px] rounded-md bg-[var(--primary)] px-4">
            <Plus className="h-4 w-4 text-white" />
            <span className="text-[13px] font-medium text-white">新增工單</span>
          </button>
        </div>

        {/* Kanban Board */}
        <main className="flex-1 overflow-auto">
          <KanbanBoard />
        </main>
      </div>
    </div>
  );
}
