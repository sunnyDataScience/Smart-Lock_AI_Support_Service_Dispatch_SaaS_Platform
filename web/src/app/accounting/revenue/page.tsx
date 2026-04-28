"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  Clock3,
  DollarSign,
  Calculator,
  CircleCheck,
  TriangleAlert,
  Calendar,
  Download,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import RevenueTrendChart from "@/components/accounting/RevenueTrendChart";
import BrandRevenueChart from "@/components/accounting/BrandRevenueChart";
import ServiceTypeChart from "@/components/accounting/ServiceTypeChart";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type RevenueSummary = components["schemas"]["RevenueSummary"];

const tabs = [
  { icon: Wallet, label: "結算管理", href: "/accounting", dot: false },
  { icon: FileText, label: "發票管理", href: "/accounting/invoices", dot: true },
  { icon: BarChart3, label: "營收報表", href: "/accounting/revenue", dot: false },
];

const segments = [
  { label: "日", value: "day", enabled: false },
  { label: "週", value: "week", enabled: false },
  { label: "月", value: "month", enabled: true },
];

function formatTwd(amount: string | undefined | null): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatPercent(rate: number | null | undefined): string {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export default function RevenuePage() {
  const pathname = usePathname();
  const [data, setData] = useState<RevenueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<RevenueSummary>("/api/v1/reports/revenue", {
        query: { granularity: "month" },
      });
      setData(res);
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
    fetchSummary();
  }, []);

  const kpis = data?.kpis;
  const kpiCards = [
    {
      icon: DollarSign,
      iconColor: "#2563EB",
      iconBg: "#DBEAFE",
      title: "本月營收",
      value: formatTwd(kpis?.month_revenue),
    },
    {
      icon: Calculator,
      iconColor: "#10B981",
      iconBg: "#D1FAE5",
      title: "平均發票金額",
      value: formatTwd(kpis?.average_invoice_amount),
    },
    {
      icon: CircleCheck,
      iconColor: "#10B981",
      iconBg: "#D1FAE5",
      title: "付款成功率",
      value: formatPercent(kpis?.paid_rate),
    },
    {
      icon: TriangleAlert,
      iconColor: "#F59E0B",
      iconBg: "#FEF3C7",
      title: "未收帳款",
      value: formatTwd(kpis?.outstanding_amount),
      sub: kpis ? `共 ${kpis.outstanding_count} 筆未收` : undefined,
      subColor: "#F59E0B",
    },
  ];

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between px-8 pt-4 pb-3">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                財務結算管理
              </h1>
              <button
                onClick={fetchSummary}
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
            </div>
            <div className="flex items-center gap-[6px]">
              <Clock3 className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
                  : "—"}
              </span>
            </div>
          </div>

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

        <div className="mx-8 mt-4 rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
          KPI / 月度趨勢 / 品牌占比為 getRevenueSummary 即時資料。
          服務類型分佈、CSV/Excel 匯出、日 / 週粒度與日期範圍待 invoice
          欄位收斂與匯出 endpoint 上線後接入。
        </div>

        {/* Scrollable Content */}
        <div className="flex flex-1 flex-col overflow-auto">
          {/* KPI Cards */}
          <div className="flex gap-4 px-8 py-5">
            {kpiCards.map((card) => (
              <div
                key={card.title}
                className="flex flex-1 items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
              >
                <div
                  className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl"
                  style={{ backgroundColor: card.iconBg }}
                >
                  <card.icon className="h-6 w-6" style={{ color: card.iconColor }} />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                    {card.title}
                  </span>
                  <span className="font-['IBM_Plex_Mono'] text-[22px] font-bold text-[var(--text-primary)]">
                    {card.value}
                  </span>
                  {card.sub && (
                    <span
                      className="text-[13px] font-medium"
                      style={{ color: card.subColor }}
                    >
                      {card.sub}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Controls */}
          <div className="flex items-center justify-between px-8">
            <div className="flex items-center gap-4">
              <div className="flex rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                {segments.map((seg) => (
                  <button
                    key={seg.label}
                    disabled={!seg.enabled}
                    title={seg.enabled ? undefined : "即將推出"}
                    className={`rounded-md px-4 py-2 text-[13px] ${
                      seg.enabled && seg.value === data?.granularity
                        ? "bg-[var(--primary)] font-semibold text-white"
                        : seg.enabled
                          ? "font-medium text-[var(--text-secondary)]"
                          : "cursor-not-allowed font-medium text-[var(--text-disabled)] opacity-60"
                    }`}
                  >
                    {seg.label}
                  </button>
                ))}
              </div>

              <button
                disabled
                title="即將推出"
                className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 opacity-60"
              >
                <Calendar className="h-4 w-4 text-[var(--text-disabled)]" />
                <span className="text-[13px] text-[var(--text-disabled)]">
                  日期範圍
                </span>
              </button>
            </div>
          </div>

          {/* Main Chart */}
          <div className="px-8 pt-4">
            <RevenueTrendChart items={data?.trend ?? []} loading={loading} />
          </div>

          {/* Bottom Charts Row */}
          <div className="flex gap-4 px-8 py-4" style={{ minHeight: 320 }}>
            <BrandRevenueChart items={data?.by_brand ?? []} loading={loading} />
            <ServiceTypeChart />
          </div>

          {/* Export Controls */}
          <div className="flex items-center justify-end gap-3 px-8 py-3">
            <button
              disabled
              title="即將推出"
              className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-4 py-[10px] opacity-60"
            >
              <Download className="h-4 w-4 text-[var(--text-disabled)]" />
              <span className="text-sm font-medium text-[var(--text-disabled)]">
                CSV匯出
              </span>
            </button>
            <button
              disabled
              title="即將推出"
              className="flex cursor-not-allowed items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-[10px] opacity-60"
            >
              <Download className="h-4 w-4 text-white" />
              <span className="text-sm font-medium text-white">Excel匯出</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
