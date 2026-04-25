"use client";

import { RefreshCw, Wallet, FileText, BarChart3, Calendar, ChevronDown } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import SettlementTable from "@/components/accounting/SettlementTable";

const tabs = [
  {
    icon: Wallet,
    label: "結算管理",
    active: true,
    dot: false,
  },
  {
    icon: FileText,
    label: "發票管理",
    active: false,
    dot: true,
  },
  {
    icon: BarChart3,
    label: "營收報表",
    active: false,
    dot: false,
  },
];

const segments = [
  { label: "月結(5號)", active: true },
  { label: "雙週結", active: false },
  { label: "週結", active: false },
];

export default function AccountingPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          {/* Header Row */}
          <div className="flex items-center justify-between px-8 py-5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                財務結算管理
              </h1>
              <RefreshCw className="h-5 w-5 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                最後更新：2026/04/22 14:30
              </span>
            </div>
          </div>

          {/* Tab Bar */}
          <div className="flex border-b border-[var(--border)] px-8">
            {tabs.map((tab) => (
              <div
                key={tab.label}
                className={`flex items-center gap-2 px-4 py-3 ${
                  tab.active
                    ? "border-b-2 border-[var(--primary)]"
                    : ""
                }`}
              >
                <tab.icon
                  className={`h-[18px] w-[18px] ${
                    tab.active
                      ? "text-[var(--primary)]"
                      : "text-[var(--text-secondary)]"
                  }`}
                />
                <span
                  className={`text-sm ${
                    tab.active
                      ? "font-semibold text-[var(--primary)]"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {tab.label}
                </span>
                {tab.dot && (
                  <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Settlement Period Selector */}
        <div className="flex items-center gap-4 px-8 py-4">
          {/* Month Dropdown */}
          <button className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-2">
            <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              2026年04月
            </span>
            <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>

          {/* Segmented Control */}
          <div className="flex rounded-md bg-[#F1F5F9] p-[3px]">
            {segments.map((seg) => (
              <button
                key={seg.label}
                className={`rounded px-[14px] py-[6px] text-[13px] ${
                  seg.active
                    ? "bg-[var(--bg-surface)] font-semibold text-[var(--text-primary)] shadow-sm"
                    : "font-medium text-[var(--text-secondary)]"
                }`}
              >
                {seg.label}
              </button>
            ))}
          </div>

          {/* Period Text */}
          <span className="text-[13px] text-[var(--text-secondary)]">
            結算期間：2026/04/01 - 2026/04/30
          </span>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Total Badge */}
          <div className="rounded-lg bg-[var(--primary)] px-5 py-[10px]">
            <span className="text-lg font-bold text-white">NT$ 892,400</span>
          </div>
        </div>

        {/* Settlement Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <SettlementTable />
        </div>
      </div>
    </div>
  );
}
