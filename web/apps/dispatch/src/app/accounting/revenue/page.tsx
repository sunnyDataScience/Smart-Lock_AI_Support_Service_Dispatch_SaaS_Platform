"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  BookText,
  Clock3,
  DollarSign,
  Calculator,
  CircleCheck,
  TriangleAlert,
  Calendar,
  Download,
} from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import RevenueTrendChart from "@/components/accounting/RevenueTrendChart";
import BrandRevenueChart from "@/components/accounting/BrandRevenueChart";
import CategoryRevenueChart from "@/components/accounting/CategoryRevenueChart";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import type { components } from "@shared/types/api.generated";

type RevenueSummary = components["schemas"]["RevenueSummary"];
// by_category 為後端 additive 欄位（問題類別營收佔比）。openapi.yaml / api.generated.ts
// 待 TS 產生器修復後同步，目前以 inline 型別消費（與 customer-stats 同策略）。
type RevenueByCategoryPoint = { category: string; revenue: string; share: number };
type RevenueSummaryWithCategory = RevenueSummary & {
  by_category?: RevenueByCategoryPoint[];
};

function formatTwd(amount: string | undefined | null): string {
  if (!amount) return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return `NT$ ${amount}`;
  return `NT$ ${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function exportTrendCsv(
  trend: any[],
  granularity: string,
  ext: "csv" | "xlsx" = "csv",
): void {
  if (!trend || trend.length === 0) return;
  const headers = ["period", "revenue", "order_count"];
  const rows = trend.map((p) => [p.period, p.revenue ?? 0, p.order_count ?? 0]);
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const ts = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `revenue-${granularity}-${ts}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function formatPercent(rate: number | null | undefined): string {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export default function RevenuePage() {
  const pathname = usePathname();
  const tPage = useTranslations("accounting");
  const tTabs = useTranslations("accounting.tabs");
  const tCommon = useTranslations("accounting.common");
  const tR = useTranslations("accounting.revenue");

  const tabs = useMemo(
    () => [
      { icon: Wallet, label: tTabs("settlements"), href: "/accounting", dot: false },
      { icon: FileText, label: tTabs("invoices"), href: "/accounting/invoices", dot: true },
      { icon: BookText, label: tTabs("vouchers"), href: "/accounting/vouchers", dot: false },
      { icon: BarChart3, label: tTabs("revenue"), href: "/accounting/revenue", dot: false },
    ],
    [tTabs],
  );

  const [data, setData] = useState<RevenueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  // 後端 /reports/revenue 目前忽略 granularity（恆回月度），且無日期範圍參數。
  // 原「日/週/月」分段與「日期範圍」下拉皆為死控制（選了資料不變），已移除；
  // 此處固定月度，待後端支援粒度/日期範圍再恢復控制項。
  const granularity = "month";

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<RevenueSummary>(tenantPath("/reports/revenue"), {
        query: { granularity },
      });
      setData(res);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [granularity]);

  const byCategory =
    (data as RevenueSummaryWithCategory | null)?.by_category ?? [];

  const kpis = data?.kpis;
  const kpiCards = [
    {
      icon: DollarSign,
      iconColor: "#2563EB",
      iconBg: "#DBEAFE",
      title: tR("kpiMonthRevenue"),
      value: formatTwd(kpis?.month_revenue),
    },
    {
      icon: Calculator,
      iconColor: "#10B981",
      iconBg: "#D1FAE5",
      title: tR("kpiAvgInvoice"),
      value: formatTwd(kpis?.average_invoice_amount),
    },
    {
      icon: CircleCheck,
      iconColor: "#10B981",
      iconBg: "#D1FAE5",
      title: tR("kpiPaidRate"),
      value: formatPercent(kpis?.paid_rate),
    },
    {
      icon: TriangleAlert,
      iconColor: "#F59E0B",
      iconBg: "#FEF3C7",
      title: tR("kpiOutstanding"),
      value: formatTwd(kpis?.outstanding_amount),
      sub: kpis ? tR("kpiOutstandingSub", { count: kpis.outstanding_count }) : undefined,
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
                {tPage("pageTitle")}
              </h1>
              <button
                onClick={fetchSummary}
                disabled={loading}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title={tCommon("refresh")}
              >
                <RefreshCw
                  className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
                />
              </button>
              {/* CSV 匯出移至頂部 header，比照 /accounting 結算頁置於 refresh 旁；
                  功能不變（客戶端月度趨勢 CSV 下載），無資料時 disabled。*/}
              <button
                onClick={() => exportTrendCsv(data?.trend ?? [], granularity)}
                disabled={!data}
                title={tR("exportCsv")}
                className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Download className="h-4 w-4 text-[var(--text-secondary)]" />
                <span className="text-[13px] text-[var(--text-primary)]">
                  {tR("exportCsv")}
                </span>
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
            </div>
            <div className="flex items-center gap-[6px]">
              <Clock3 className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? tCommon("lastUpdated", {
                      time: updatedAt.toLocaleTimeString("zh-TW", { hour12: false }),
                    })
                  : tCommon("dash")}
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

          {/* 原「日/週/月粒度」分段與「日期範圍」下拉已移除：後端 /reports/revenue
              忽略 granularity（恆回月度）、無日期範圍參數，兩者皆為死控制。待後端
              支援後再恢復。月度趨勢圖直接呈現。*/}

          {/* Main Chart */}
          <div className="px-8 pt-4">
            <RevenueTrendChart items={data?.trend ?? []} loading={loading} />
          </div>

          {/* Bottom Charts Row — shrink-0 防 flex column 捲動容器把本列壓到 floor。
              注意：原 inline style={{minHeight:320}} 會覆蓋 flex item 預設 min-height:auto、
              「放行」壓縮（4 列舊圖剛好塞得下、8 列問題類別圖被壓到 320 → 內容溢出跑版）。
              改 min-h-[320px]（空資料地板）+ shrink-0（高度回到內容自然值）。*/}
          <div className="flex shrink-0 gap-4 px-8 py-4 min-h-[320px]">
            <BrandRevenueChart items={data?.by_brand ?? []} loading={loading} />
            <CategoryRevenueChart items={byCategory} loading={loading} />
          </div>
        </div>
      </div>
    </div>
  );
}
