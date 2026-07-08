"use client";

import { useMemo, useState } from "react";
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
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { auth, getCurrentSession } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type Invoice = components["schemas"]["Invoice"];

function formatInvoiceError(e: unknown): string {
  return friendlyError(e);
}

export default function InvoicesPage() {
  const pathname = usePathname();
  const tPage = useTranslations("accounting");
  const tTabs = useTranslations("accounting.tabs");
  const tCommon = useTranslations("accounting.common");
  const tInv = useTranslations("accounting.invoices");

  const session = getCurrentSession();
  const tenantId = session?.tenantId ?? auth.getTenantId();

  const tabs = useMemo(
    () => [
      { icon: Wallet, label: tTabs("settlements"), href: "/accounting", dot: false },
      { icon: FileText, label: tTabs("invoices"), href: "/accounting/invoices", dot: true },
      { icon: BookText, label: tTabs("vouchers"), href: "/accounting/vouchers", dot: false },
      { icon: BarChart3, label: tTabs("revenue"), href: "/accounting/revenue", dot: false },
    ],
    [tTabs],
  );

  const [keyword, setKeyword] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [periodFilter, setPeriodFilter] = useState<string>("");
  const [paymentMethodFilter, setPaymentMethodFilter] = useState<string>("");

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (keyword) p.set("keyword", keyword);
    if (statusFilter) p.set("status", statusFilter);
    if (paymentMethodFilter) p.set("payment_method", paymentMethodFilter);
    if (periodFilter) {
      const days = parseInt(periodFilter, 10);
      if (!Number.isNaN(days)) {
        const since = new Date(Date.now() - days * 24 * 3600 * 1000);
        p.set("created_after", since.toISOString());
      }
    }
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  }, [keyword, statusFilter, periodFilter, paymentMethodFilter]);

  const {
    items,
    cursor: nextCursor,
    hasMore,
    lastFetchedAt: updatedAt,
    loading,
    error,
    loadMore,
    refresh,
  } = usePaginatedFetch<Invoice>({
    path: `/tenants/${encodeURIComponent(tenantId)}/accounting/invoices${queryString}`,
    pageSize: 50,
    formatError: formatInvoiceError,
  });

  const totalLabel = hasMore
    ? tCommon("totalCountPlus", { count: items.length })
    : tCommon("totalCount", { count: items.length });

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between px-8 py-5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                {tPage("pageTitle")}
              </h1>
              <button
                onClick={refresh}
                disabled={loading}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title={tCommon("refresh")}
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
                {error ? tCommon("disconnected") : tCommon("connected")}
              </span>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? tCommon("lastUpdated", {
                      time: updatedAt.toLocaleTimeString("zh-TW", { hour12: false }),
                    })
                  : tCommon("dash")}
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

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          {/* Search */}
          <div className="flex h-[38px] w-[320px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={tInv("searchPlaceholder")}
              className="flex-1 bg-transparent text-[13px] outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            {/* 值對齊後端 InvoiceStatus 白名單（pending/issued/voided）。
                原 paid/overdue 非合法 filter 值（送出即 422）：API 無法區分
                已付款 vs 已開立（issued 含 paid），overdue 也非狀態而是衍生條件。*/}
            <option value="">{tInv("filterAllStatus")}</option>
            <option value="pending">草稿（待開立）</option>
            <option value="issued">已開立</option>
            <option value="voided">已作廢</option>
          </select>

          <select
            value={paymentMethodFilter}
            onChange={(e) => setPaymentMethodFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tInv("filterPaymentMethod")}</option>
            <option value="credit_card">信用卡</option>
            <option value="bank_transfer">銀行轉帳</option>
            <option value="cash">現金</option>
            <option value="line_pay">LINE Pay</option>
            <option value="other">其他</option>
          </select>

          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="h-[38px] rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tInv("dateRange")}</option>
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
            <option value="90">最近 90 天</option>
          </select>

        </div>

        {/* Invoices Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <InvoicesTable items={items} loading={loading} />

          {hasMore && (
            <div className="flex justify-center py-4">
              <button
                onClick={loadMore}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? tCommon("loading") : tCommon("loadMore")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
