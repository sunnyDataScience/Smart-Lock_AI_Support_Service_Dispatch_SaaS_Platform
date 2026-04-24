"use client";

import { ChevronDown, Calendar, Search, X } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ProblemCardsTable from "@/components/problem-cards/ProblemCardsTable";

const summaryBadges = [
  { label: "待處理", count: 28, color: "#6366F1", bg: "#EEF2FF" },
  { label: "診斷中", count: 15, color: "#2563EB", bg: "#DBEAFE" },
  { label: "已解決", count: 142, color: "#10B981", bg: "#D1FAE5" },
  { label: "已升級", count: 8, color: "#EF4444", bg: "#FEE2E2" },
];

const filters = [
  { label: "狀態篩選", hasIcon: false },
  { label: "解決層級", hasIcon: false },
  { label: "品牌", hasIcon: false },
];

export default function ProblemCardsPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 問題卡片
            </span>
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              問題卡片管理
            </h1>
          </div>

          <div className="flex items-center gap-3">
            {summaryBadges.map((badge) => (
              <div
                key={badge.label}
                className="flex items-center gap-[6px] rounded-md px-3 py-[6px]"
                style={{ backgroundColor: badge.bg }}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: badge.color }}
                />
                <span
                  className="text-[13px] font-medium"
                  style={{ color: badge.color }}
                >
                  {badge.label}
                </span>
                <span
                  className="text-[13px] font-bold"
                  style={{ color: badge.color }}
                >
                  {badge.count}
                </span>
              </div>
            ))}

            <div className="h-6 w-px bg-[var(--border)]" />

            <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                共
              </span>
              <span className="text-[13px] font-bold text-[var(--text-primary)]">
                193
              </span>
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                張卡片
              </span>
            </div>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          {filters.map((f) => (
            <button
              key={f.label}
              className="flex h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3"
            >
              <span className="text-[13px] text-[var(--text-secondary)]">
                {f.label}
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          ))}

          <button className="flex h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3">
            <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[13px] text-[var(--text-secondary)]">
              日期範圍: 近30天
            </span>
            <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>

          <div className="flex h-9 flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              placeholder="搜尋症狀描述..."
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          <button className="flex h-9 items-center gap-[6px] px-3">
            <X className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">
              清除篩選
            </span>
          </button>
        </div>

        {/* Table */}
        <main className="flex-1 overflow-auto bg-[var(--bg-page)]">
          <ProblemCardsTable />
        </main>
      </div>
    </div>
  );
}
