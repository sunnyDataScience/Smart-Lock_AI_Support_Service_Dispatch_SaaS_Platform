"use client";

import { useEffect, useState } from "react";
import {
  RotateCw,
  Calendar,
  ChevronDown,
  Download,
} from "lucide-react";
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import Sidebar from "@/components/layout/Sidebar";
import DateRangePicker from "@/components/ui/DateRangePicker";
import { getPresetRange, type DateRange } from "@/lib/dateRange";
import { ApiError, api, auth } from "@/lib/api";
import type { components } from "@/types/api.generated";
import { ReportExportModal } from "@/components/admin/reports/ReportExportModal";

type RevenueSummary = components["schemas"]["RevenueSummary"];
type RevenueTrendPoint = components["schemas"]["RevenueTrendPoint"];
type RevenueByBrandPoint = components["schemas"]["RevenueByBrandPoint"];

const segments = [
  { label: "日", active: false },
  { label: "週", active: false },
  { label: "月", active: true },
  { label: "季", active: false },
];

const formatRevenueAxis = (value: number) => {
  if (value === 0) return "0";
  if (value >= 10000) return `${(value / 10000).toFixed(0)}萬`;
  return value.toLocaleString();
};

const formatNtd = (decimalStr: string | null | undefined) => {
  if (decimalStr == null) return "—";
  const n = Number(decimalStr);
  if (!Number.isFinite(n)) return "—";
  return `NT$${Math.round(n).toLocaleString()}`;
};

const formatPercent = (rate: number | null | undefined) => {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
};

const periodLabel = (period: string): string => {
  const m = /^\d{4}-(\d{2})$/.exec(period);
  if (!m) return period;
  return `${parseInt(m[1], 10)}月`;
};

function buildChartData(trend: RevenueTrendPoint[]) {
  return trend.map((p) => ({
    month: periodLabel(p.period),
    current: Number(p.revenue ?? 0),
    order_count: p.order_count,
  }));
}

function totalRevenue(trend: RevenueTrendPoint[]): number {
  return trend.reduce((acc, p) => acc + Number(p.revenue ?? 0), 0);
}

function totalOrders(trend: RevenueTrendPoint[]): number {
  return trend.reduce((acc, p) => acc + (p.order_count ?? 0), 0);
}

function buildBrandRows(byBrand: RevenueByBrandPoint[]) {
  return byBrand.map((b) => ({
    brand: b.brand,
    revenue: formatNtd(b.revenue),
    share: `${(b.share * 100).toFixed(1)}%`,
    rawShare: b.share,
  }));
}

export default function RevenueReportPage() {
  // 日期範圍 — 預設「過去 30 日」。
  // TODO[E7x §4.3]: /api/v1/reports/revenue 目前只支援 granularity=month，
  // 還沒有 from/to 參數；range state 暫時只控制 UI，實際 API 仍 fetch 近 12 月。
  const [range, setRange] = useState<DateRange>(() => getPresetRange("last30"));
  const [summary, setSummary] = useState<RevenueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [exportOpen, setExportOpen] = useState(false);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      // v2 tenant-scoped path（FR-0021 / CR-0003 P2-W1）
      const tenantId = auth.getTenantId();
      const res = await api.get<RevenueSummary>(
        `/tenants/${encodeURIComponent(tenantId)}/reports/revenue`,
        { query: { granularity: "month" } },
      );
      setSummary(res);
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

  const trend = summary?.trend ?? [];
  const byBrand = summary?.by_brand ?? [];
  const kpis = summary?.kpis;
  const chartData = buildChartData(trend);
  const brandRows = buildBrandRows(byBrand);
  const sumRevenue = totalRevenue(trend);
  const sumOrders = totalOrders(trend);
  const avgPerOrder = sumOrders > 0 ? sumRevenue / sumOrders : 0;
  const updatedLabel = updatedAt
    ? `資料更新於 ${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
    : "尚未載入";

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--text-secondary)]">
                首頁 &gt; 報表中心 &gt; 營收
              </span>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                營收報表
              </h1>
              <span className="text-xs text-[var(--text-secondary)]">
                {updatedLabel}（granularity = month）
              </span>
            </div>
            <button
              onClick={fetchSummary}
              disabled={loading}
              className="rounded-md p-2 hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title="重新整理"
            >
              <RotateCw
                className={`h-4 w-4 text-[var(--text-secondary)] ${
                  loading ? "animate-spin" : ""
                }`}
              />
            </button>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入營收資料失敗：{error}
            </div>
          )}

          <div className="flex items-center gap-3">
            <div className="flex rounded-lg bg-[#E2E8F0] p-[3px]">
              {segments.map((seg) => (
                <button
                  key={seg.label}
                  disabled={!seg.active}
                  title={seg.active ? "" : "即將推出"}
                  className={`rounded-md px-[14px] py-[6px] text-[13px] ${
                    seg.active
                      ? "bg-[var(--primary)] font-semibold text-white"
                      : "cursor-not-allowed text-[var(--text-disabled)] opacity-60"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <DateRangePicker value={range} onChange={setRange} />

            <button
              disabled
              title="即將推出"
              className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[#CBD5E1] bg-[var(--bg-page)] px-3 py-[7px] opacity-60"
            >
              <span className="text-[13px] text-[var(--text-disabled)]">
                切片：按品牌
              </span>
              <ChevronDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
            </button>

            <div
              className="flex items-center gap-2 opacity-60"
              title="即將推出"
            >
              <div className="relative h-5 w-9 rounded-full bg-[#CBD5E1]">
                <div className="absolute left-[2px] top-[2px] h-4 w-4 rounded-full bg-white" />
              </div>
              <span className="text-[13px] text-[var(--text-disabled)]">
                與上期比較
              </span>
            </div>

            <div className="flex-1" />

            <button
              onClick={() => setExportOpen(true)}
              title="匯出 CSV"
              className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-[14px] py-[7px] hover:opacity-90"
            >
              <Download className="h-[14px] w-[14px] text-white" />
              <span className="text-[13px] font-semibold text-white">匯出</span>
            </button>

            <button
              disabled
              title="即將推出"
              className="flex cursor-not-allowed items-center gap-[6px] rounded-lg border border-[#CBD5E1] bg-[var(--bg-page)] px-[14px] py-[7px] opacity-60"
            >
              <Calendar className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
              <span className="text-[13px] text-[var(--text-disabled)]">
                排程發送
              </span>
            </button>
          </div>

          <div className="flex flex-col gap-5 rounded-xl border border-[#E2E8F0] bg-[var(--bg-surface)] p-6">
            <span className="text-lg font-semibold text-[var(--text-primary)]">
              營收趨勢
            </span>

            <div className="flex gap-6">
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">本月營收</span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {formatNtd(kpis?.month_revenue)}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">已開立工單（近 12 月）</span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {summary ? sumOrders : "—"}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">平均客單</span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {summary && sumOrders > 0
                    ? `NT$${Math.round(avgPerOrder).toLocaleString()}`
                    : "—"}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">付款成功率</span>
                <span className="text-xl font-bold text-[#10B981]">
                  {formatPercent(kpis?.paid_rate)}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">未收帳款</span>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold text-[#D97706]">
                    {formatNtd(kpis?.outstanding_amount)}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {kpis?.outstanding_count != null
                      ? `${kpis.outstanding_count} 筆`
                      : ""}
                  </span>
                </div>
              </div>
            </div>

            <div className="h-[220px] w-full">
              {loading && summary === null ? (
                <div className="flex h-full items-center justify-center text-sm text-[var(--text-secondary)]">
                  載入中…
                </div>
              ) : chartData.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-[var(--text-secondary)]">
                  近 12 個月尚無已開立 invoice
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={chartData}
                    margin={{ top: 0, right: 10, left: 10, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="0"
                      stroke="#F1F5F9"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="month"
                      tick={{ fontSize: 10, fill: "#64748B" }}
                      axisLine={{ stroke: "#E2E8F0" }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={formatRevenueAxis}
                    />
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        `NT$ ${value.toLocaleString()}`,
                        name === "current" ? "本期營收" : name,
                      ]}
                    />
                    <Bar
                      dataKey="current"
                      fill="#2563EB"
                      radius={[4, 4, 0, 0]}
                      barSize={20}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="flex items-center justify-center gap-4">
              <div className="flex items-center gap-[6px]">
                <div className="h-3 w-3 rounded-sm bg-[#2563EB]" />
                <span className="text-xs text-[var(--text-secondary)]">
                  本期營收（已開立 invoice）
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-4 rounded-xl border border-[#E2E8F0] bg-[var(--bg-surface)] p-6">
            <div className="flex items-center">
              <span className="text-lg font-semibold text-[var(--text-primary)]">
                品牌營收占比
              </span>
              <div className="flex-1" />
              <span className="text-xs text-[var(--text-secondary)]">
                樞紐切片：時間 × 品牌（待後端 endpoint 擴充後上線）
              </span>
            </div>

            <div className="overflow-hidden rounded-lg border border-[#E2E8F0]">
              <div className="flex bg-[#F1F5F9]">
                <div className="w-[180px] px-3 py-[10px]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    品牌
                  </span>
                </div>
                <div className="flex-1 px-3 py-[10px]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    營收（近 12 月已開立）
                  </span>
                </div>
                <div className="flex-1 px-3 py-[10px]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    占比
                  </span>
                </div>
                <div className="flex-1 px-3 py-[10px]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    占比視覺
                  </span>
                </div>
              </div>

              {loading && summary === null ? (
                <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
                  載入中…
                </div>
              ) : brandRows.length === 0 ? (
                <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
                  暫無品牌營收資料
                </div>
              ) : (
                brandRows.map((row, idx) => (
                  <div
                    key={row.brand}
                    className={`flex items-center ${idx % 2 === 1 ? "bg-[var(--bg-page)]" : ""}`}
                  >
                    <div className="w-[180px] px-3 py-2">
                      <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        {row.brand}
                      </span>
                    </div>
                    <div className="flex-1 px-3 py-2">
                      <span className="text-[13px] text-[var(--text-primary)]">
                        {row.revenue}
                      </span>
                    </div>
                    <div className="flex-1 px-3 py-2">
                      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                        {row.share}
                      </span>
                    </div>
                    <div className="flex-1 px-3 py-2">
                      <div className="h-[6px] w-full max-w-[200px] overflow-hidden rounded-full bg-[#E2E8F0]">
                        <div
                          className="h-full rounded-full bg-[#2563EB]"
                          style={{
                            width: `${Math.round(row.rawShare * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-[var(--text-secondary)]">
                共 {brandRows.length} 個品牌
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                {updatedLabel}
              </span>
            </div>
          </div>
        </div>
      </div>

      <ReportExportModal
        open={exportOpen}
        onOpenChange={setExportOpen}
        reportType="revenue"
        filters={{
          granularity: "month",
          from: range.from ? toDateOnly(range.from) : undefined,
          to: range.to ? toDateOnly(range.to) : undefined,
        }}
      />
    </div>
  );
}

function toDateOnly(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
