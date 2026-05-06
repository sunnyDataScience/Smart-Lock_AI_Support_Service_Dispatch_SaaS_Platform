"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  BookText,
  Search,
  ChevronDown,
  Calendar,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import InvoicesTable from "@/components/accounting/InvoicesTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Invoice = components["schemas"]["Invoice"];
type InvoicePage = components["schemas"]["InvoicePage"];

const tabs = [
  { icon: Wallet, label: "結算管理", href: "/accounting", dot: false },
  { icon: FileText, label: "發票管理", href: "/accounting/invoices", dot: true },
  { icon: BookText, label: "會計傳票", href: "/accounting/vouchers", dot: false },
  { icon: BarChart3, label: "營收報表", href: "/accounting/revenue", dot: false },
];

const filterDropdowns = [
  { label: "全部狀態" },
  { label: "付款方式" },
];

export default function InvoicesPage() {
  const pathname = usePathname();
  const [items, setItems] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchInvoices = async (opts?: { append?: boolean; cursor?: string | null }) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      if (opts?.cursor) query.cursor = opts.cursor;
      const res = await api.get<InvoicePage>("/api/v1/accounting/invoices", {
        query,
      });
      const newItems = res.items ?? [];
      setItems((prev) => (opts?.append ? [...prev, ...newItems] : newItems));
      setNextCursor(res.next_cursor ?? null);
      setHasMore(res.has_more ?? false);
      setUpdatedAt(new Date());
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
    fetchInvoices();
  }, []);

  const totalLabel = `共 ${items.length}${hasMore ? "+" : ""} 筆`;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between px-8 py-5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                財務結算管理
              </h1>
              <button
                onClick={() => fetchInvoices()}
                disabled={loading}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title="重新整理"
              >
                <RefreshCw
                  className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
                />
              </button>
              <span
                className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
                style={{
                  backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                  color: error ? "#B91C1C" : "#15803D",
                }}
              >
                <span
                  className="h-[6px] w-[6px] rounded-full"
                  style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
                />
                {error ? "連線失敗" : "已連線"}
              </span>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
                  : "—"}
              </span>
              <span className="text-[13px] text-[var(--text-secondary)]">·</span>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {totalLabel}
              </span>
            </div>
          </div>

          {/* Tab Bar */}
          <div className="flex border-b border-[var(--border)] px-8">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              return (
                <Link
                  key={tab.label}
                  href={tab.href}
                  className={`flex items-center gap-2 px-4 py-3 ${
                    isActive ? "border-b-2 border-[var(--primary)]" : ""
                  }`}
                >
                  <tab.icon
                    className={`h-[18px] w-[18px] ${
                      isActive ? "text-[var(--primary)]" : "text-[var(--text-secondary)]"
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
                </Link>
              );
            })}
          </div>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Banner */}
        <div className="mx-8 mt-4 rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
          表格為 listInvoices 即時資料。搜尋 / 狀態 / 付款方式 / 日期範圍 /
          僅顯示逾期 待 invoice 寫入 endpoints 與篩選欄位收斂後接入。
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          {/* Search */}
          <div
            className="flex h-[38px] w-[320px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60"
            title="即將推出"
          >
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              disabled
              type="text"
              placeholder="搜尋發票編號、客戶名稱..."
              className="flex-1 cursor-not-allowed bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          {filterDropdowns.map((dd) => (
            <button
              key={dd.label}
              disabled
              title="即將推出"
              className="flex h-[38px] cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60"
            >
              <span className="text-[13px] text-[var(--text-disabled)]">
                {dd.label}
              </span>
              <ChevronDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
            </button>
          ))}

          <button
            disabled
            title="即將推出"
            className="flex h-[38px] cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60"
          >
            <Calendar className="h-4 w-4 text-[var(--text-disabled)]" />
            <span className="text-[13px] text-[var(--text-disabled)]">
              日期範圍
            </span>
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
          </button>

          <div className="flex-1" />

          <label className="flex cursor-not-allowed items-center gap-2 opacity-60" title="即將推出">
            <div className="flex h-5 w-9 items-center rounded-full bg-[var(--border)] px-[2px]">
              <div className="h-4 w-4 rounded-full bg-white shadow-sm" />
            </div>
            <span className="text-[13px] text-[var(--text-disabled)]">
              僅顯示逾期
            </span>
          </label>
        </div>

        {/* Invoices Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <InvoicesTable items={items} loading={loading} />

          {hasMore && (
            <div className="flex justify-center py-4">
              <button
                onClick={() => fetchInvoices({ append: true, cursor: nextCursor })}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
