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
  Calendar,
  Download,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, auth, getCurrentSession } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type Voucher = components["schemas"]["Voucher"];
type RelatedEntityType = NonNullable<Voucher["related_entity_type"]>;

function formatVoucherError(e: unknown): string {
  return friendlyError(e);
}

const ENTITY_BADGE: Record<RelatedEntityType, { bg: string; text: string }> = {
  reconciliation: { bg: "#DBEAFE", text: "#2563EB" },
  settlement: { bg: "#DCFCE7", text: "#15803D" },
  refund: { bg: "#FEE2E2", text: "#B91C1C" },
  invoice: { bg: "#EDE9FE", text: "#6D28D9" },
};

function formatAmount(amount: string): { display: string; isNegative: boolean } {
  const num = parseFloat(amount);
  const isNegative = num < 0;
  const formatted = Math.abs(num).toLocaleString("zh-TW", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return { display: `${isNegative ? "-" : ""}NT$ ${formatted}`, isNegative };
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function VouchersPage() {
  const pathname = usePathname();
  const tPage = useTranslations("accounting");
  const tTabs = useTranslations("accounting.tabs");
  const tCommon = useTranslations("accounting.common");
  const tV = useTranslations("accounting.vouchers");

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const session = getCurrentSession();
  const tenantId = session?.tenantId ?? auth.getTenantId();

  const tabs = useMemo(
    () => [
      { icon: Wallet, label: tTabs("settlements"), href: "/accounting" },
      { icon: FileText, label: tTabs("invoices"), href: "/accounting/invoices" },
      { icon: BookText, label: tTabs("vouchers"), href: "/accounting/vouchers" },
      { icon: BarChart3, label: tTabs("revenue"), href: "/accounting/revenue" },
    ],
    [tTabs],
  );

  const ENTITY_LABEL: Record<RelatedEntityType, string> = useMemo(
    () => ({
      reconciliation: tV("entityReconciliation"),
      settlement: tV("entitySettlement"),
      refund: tV("entityRefund"),
      invoice: tV("entityInvoice"),
    }),
    [tV],
  );

  const [startDate, setStartDate] = useState<string>(isoDaysAgo(30));
  const [endDate, setEndDate] = useState<string>(todayIso());
  const [exporting, setExporting] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    items,
    cursor: nextCursor,
    hasMore,
    lastFetchedAt: updatedAt,
    loading,
    error: fetchError,
    loadMore,
    refresh,
  } = usePaginatedFetch<Voucher>({
    path: `/tenants/${encodeURIComponent(tenantId)}/vouchers`,
    pageSize: 50,
    query: {
      posting_date_start: startDate || undefined,
      posting_date_end: endDate || undefined,
    },
    queryKey: `range=${startDate}~${endDate}`,
    formatError: formatVoucherError,
  });

  // page-level error 合併 list fetch error 與 action (export) error
  const error = fetchError || actionError;

  const handleExport = async (voucher: Voucher) => {
    if (exporting) return;
    setExporting(voucher.id);
    setActionError(null);
    try {
      await api.download(
        `/tenants/${encodeURIComponent(tenantId)}/vouchers/${voucher.id}/export`,
        { filename: `voucher_${voucher.voucher_number}.pdf` },
      );
    } catch (e) {
      setActionError(formatVoucherError(e));
    } finally {
      setExporting(null);
    }
  };

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
                </Link>
              );
            })}
          </div>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate || undefined}
              aria-label={tV("filterStartLabel")}
              className="h-[38px] rounded-md border border-[var(--border)] bg-white px-3 text-[13px] text-[var(--text-primary)]"
            />
            <span className="text-[13px] text-[var(--text-secondary)]">{tV("filterTo")}</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate || undefined}
              aria-label={tV("filterEndLabel")}
              className="h-[38px] rounded-md border border-[var(--border)] bg-white px-3 text-[13px] text-[var(--text-primary)]"
            />
            {(startDate || endDate) && (
              <button
                onClick={() => {
                  setStartDate("");
                  setEndDate("");
                }}
                className="text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                {tV("filterClear")}
              </button>
            )}
          </div>
        </div>

        {/* Vouchers Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <div className="mx-8 mt-4 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              <div className="w-[160px] text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colVoucherNo")}
              </div>
              <div className="w-[120px] text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colType")}
              </div>
              <div className="w-[120px] text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colDate")}
              </div>
              <div className="w-[100px] text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colDebit")}
              </div>
              <div className="w-[100px] text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colCredit")}
              </div>
              <div className="w-[160px] text-right text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colAmount")}
              </div>
              <div className="flex-1 pl-6 text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colMemo")}
              </div>
              <div className="w-[110px] text-right text-xs font-semibold text-[var(--text-secondary)]">
                {tV("colAction")}
              </div>
            </div>

            {items.length === 0 && !loading && (
              <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                {tV("noResults")}
              </div>
            )}

            {items.map((row) => {
              const entity = row.related_entity_type;
              const amt = formatAmount(row.amount);
              return (
                <div
                  key={row.id}
                  className="flex items-center border-t border-t-[var(--border)] px-4"
                  style={{ minHeight: 52 }}
                >
                  <div className="w-[160px] font-['IBM_Plex_Mono'] text-[13px] font-medium text-[var(--text-primary)]">
                    {row.voucher_number}
                  </div>
                  <div className="w-[120px]">
                    {entity ? (
                      <span
                        className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                        style={{
                          backgroundColor: ENTITY_BADGE[entity].bg,
                          color: ENTITY_BADGE[entity].text,
                        }}
                      >
                        {ENTITY_LABEL[entity]}
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--text-disabled)]">—</span>
                    )}
                  </div>
                  <div className="w-[120px] font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
                    {row.posting_date}
                  </div>
                  <div className="w-[100px] font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
                    {row.debit_account}
                  </div>
                  <div className="w-[100px] font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
                    {row.credit_account}
                  </div>
                  <div
                    className={`w-[160px] text-right font-['IBM_Plex_Mono'] text-[13px] font-semibold ${
                      amt.isNegative ? "text-red-600" : "text-[var(--text-primary)]"
                    }`}
                  >
                    {amt.display}
                  </div>
                  <div className="flex-1 pl-6 text-[13px] text-[var(--text-secondary)]">
                    {row.memo || tCommon("dash")}
                  </div>
                  <div className="w-[110px] text-right">
                    <button
                      onClick={() => handleExport(row)}
                      disabled={exporting === row.id}
                      className="inline-flex items-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-[10px] py-[6px] text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                      title={tV("exportTitle")}
                    >
                      <Download className="h-[12px] w-[12px]" />
                      {exporting === row.id ? tV("exporting") : tV("exportButton")}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

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
