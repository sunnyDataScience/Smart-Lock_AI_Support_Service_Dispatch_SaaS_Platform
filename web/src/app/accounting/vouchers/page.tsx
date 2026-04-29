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
  Calendar,
  Download,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Voucher = components["schemas"]["Voucher"];
type VoucherPage = components["schemas"]["VoucherPage"];
type RelatedEntityType = NonNullable<Voucher["related_entity_type"]>;

const tabs = [
  { icon: Wallet, label: "結算管理", href: "/accounting" },
  { icon: FileText, label: "發票管理", href: "/accounting/invoices" },
  { icon: BookText, label: "會計傳票", href: "/accounting/vouchers" },
  { icon: BarChart3, label: "營收報表", href: "/accounting/revenue" },
];

const ENTITY_LABEL: Record<RelatedEntityType, string> = {
  reconciliation: "對帳",
  settlement: "結算",
  refund: "退款",
  invoice: "發票",
};

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
  const [items, setItems] = useState<Voucher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [startDate, setStartDate] = useState<string>(isoDaysAgo(30));
  const [endDate, setEndDate] = useState<string>(todayIso());
  const [exporting, setExporting] = useState<string | null>(null);

  const handleExport = async (voucher: Voucher) => {
    if (exporting) return;
    setExporting(voucher.id);
    try {
      await api.download(
        `/api/v1/accounting/vouchers/${voucher.id}/export`,
        { filename: `voucher_${voucher.voucher_number}.pdf` },
      );
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setExporting(null);
    }
  };

  const fetchVouchers = async (opts?: { append?: boolean; cursor?: string | null }) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      if (opts?.cursor) query.cursor = opts.cursor;
      if (startDate) query.posting_date_start = startDate;
      if (endDate) query.posting_date_end = endDate;
      const res = await api.get<VoucherPage>("/api/v1/accounting/vouchers", {
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
    fetchVouchers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate]);

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
                onClick={() => fetchVouchers()}
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
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate || undefined}
              className="h-[38px] rounded-md border border-[var(--border)] bg-white px-3 text-[13px] text-[var(--text-primary)]"
            />
            <span className="text-[13px] text-[var(--text-secondary)]">至</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate || undefined}
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
                清除日期
              </button>
            )}
          </div>
        </div>

        {/* Vouchers Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <div className="mx-8 mt-4 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              <div className="w-[160px] text-xs font-semibold text-[var(--text-secondary)]">
                傳票編號
              </div>
              <div className="w-[120px] text-xs font-semibold text-[var(--text-secondary)]">
                類型
              </div>
              <div className="w-[120px] text-xs font-semibold text-[var(--text-secondary)]">
                入帳日
              </div>
              <div className="w-[100px] text-xs font-semibold text-[var(--text-secondary)]">
                借方
              </div>
              <div className="w-[100px] text-xs font-semibold text-[var(--text-secondary)]">
                貸方
              </div>
              <div className="w-[160px] text-right text-xs font-semibold text-[var(--text-secondary)]">
                金額
              </div>
              <div className="flex-1 pl-6 text-xs font-semibold text-[var(--text-secondary)]">
                摘要
              </div>
              <div className="w-[110px] text-right text-xs font-semibold text-[var(--text-secondary)]">
                動作
              </div>
            </div>

            {items.length === 0 && !loading && (
              <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                沒有符合條件的傳票
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
                    {row.memo || "—"}
                  </div>
                  <div className="w-[110px] text-right">
                    <button
                      onClick={() => handleExport(row)}
                      disabled={exporting === row.id}
                      className="inline-flex items-center gap-[6px] rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-[10px] py-[6px] text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                      title="匯出 PDF"
                    >
                      <Download className="h-[12px] w-[12px]" />
                      {exporting === row.id ? "匯出中…" : "PDF"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {hasMore && (
            <div className="flex justify-center py-4">
              <button
                onClick={() => fetchVouchers({ append: true, cursor: nextCursor })}
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
