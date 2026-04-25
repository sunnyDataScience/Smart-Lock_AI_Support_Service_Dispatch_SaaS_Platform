"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RefreshCw, Wallet, FileText, BarChart3, Search, ChevronDown, Calendar } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import InvoicesTable from "@/components/accounting/InvoicesTable";

const tabs = [
  {
    icon: Wallet,
    label: "結算管理",
    href: "/accounting" as string | undefined,
    dot: false,
  },
  {
    icon: FileText,
    label: "發票管理",
    href: "/accounting/invoices" as string | undefined,
    dot: true,
  },
  {
    icon: BarChart3,
    label: "營收報表",
    href: "/accounting/revenue" as string | undefined,
    dot: false,
  },
];

const filterDropdowns = [
  { label: "全部狀態", hasChevron: true },
  { label: "付款方式", hasChevron: true },
];

export default function InvoicesPage() {
  const pathname = usePathname();

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
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const content = (
                <>
                  <tab.icon
                    className={`h-[18px] w-[18px] ${
                      isActive
                        ? "text-[var(--primary)]"
                        : "text-[var(--text-secondary)]"
                    }`}
                  />
                  <span
                    className={`text-sm ${
                      isActive
                        ? "font-semibold text-[var(--primary)]"
                        : "font-medium text-[var(--text-secondary)]"
                    }`}
                  >
                    {tab.label}
                  </span>
                  {tab.dot && (
                    <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
                  )}
                </>
              );

              const className = `flex items-center gap-2 px-4 py-3 ${
                isActive ? "border-b-2 border-[var(--primary)]" : ""
              }`;

              if (tab.href) {
                return (
                  <Link key={tab.label} href={tab.href} className={className}>
                    {content}
                  </Link>
                );
              }

              return (
                <div key={tab.label} className={className}>
                  {content}
                </div>
              );
            })}
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          {/* Search */}
          <div className="flex h-[38px] w-[320px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="搜尋發票編號、客戶名稱..."
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          {/* Filter Dropdowns */}
          {filterDropdowns.map((dd) => (
            <button
              key={dd.label}
              className="flex h-[38px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3"
            >
              <span className="text-[13px] text-[var(--text-primary)]">
                {dd.label}
              </span>
              {dd.hasChevron && (
                <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              )}
            </button>
          ))}

          {/* Date Range */}
          <button className="flex h-[38px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
            <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[13px] text-[var(--text-primary)]">
              日期範圍
            </span>
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
          </button>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Overdue Toggle */}
          <label className="flex items-center gap-2">
            <div className="flex h-5 w-9 items-center rounded-full bg-[var(--border)] px-[2px]">
              <div className="h-4 w-4 rounded-full bg-white shadow-sm" />
            </div>
            <span className="text-[13px] text-[var(--text-secondary)]">
              僅顯示逾期
            </span>
          </label>
        </div>

        {/* Invoices Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <InvoicesTable />
        </div>
      </div>
    </div>
  );
}
