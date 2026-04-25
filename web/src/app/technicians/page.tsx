"use client";

import { Search, ChevronDown, Wrench, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import TechniciansTable from "@/components/technicians/TechniciansTable";

const filterDropdowns = [
  { label: "狀態", hasChevron: true },
  { label: "專長品牌", hasChevron: true },
  { label: "服務區域", hasChevron: true },
  { label: "評分 ≥ 4.0", hasChevron: true },
];

export default function TechniciansPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary)]">
              <Wrench className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col gap-[2px]">
              <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
                技師管理
              </h1>
            </div>
            <span className="ml-1 flex h-[26px] items-center rounded-full bg-[#DBEAFE] px-3 text-[13px] font-semibold text-[var(--primary)]">
              48 位技師
            </span>
          </div>

          <button className="flex h-9 items-center gap-[6px] rounded-md bg-[var(--primary)] px-4">
            <Plus className="h-4 w-4 text-white" />
            <span className="text-[13px] font-medium text-white">新增技師</span>
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          {/* Search */}
          <div className="flex h-9 w-[280px] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="搜尋技師姓名、電話..."
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          {/* Filter Dropdowns */}
          {filterDropdowns.map((dd) => (
            <button
              key={dd.label}
              className="flex h-9 items-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3"
            >
              <span className="text-[13px] text-[var(--text-primary)]">
                {dd.label}
              </span>
              {dd.hasChevron && (
                <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              )}
            </button>
          ))}
        </div>

        {/* Table Area */}
        <main className="flex flex-1 flex-col overflow-auto">
          <TechniciansTable />
        </main>
      </div>
    </div>
  );
}
