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
import {
  addDays,
  addMonths,
  endOfMonth,
  formatDateRange,
  startOfDay,
  startOfMonth,
  type DateRange,
} from "@/lib/dateRange";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { UAT_HIDE_FAKE_FLOWS } from "@/lib/uatFlags";
import type { components } from "@/types/api.generated";
import { ReportExportModal } from "@/components/admin/reports/ReportExportModal";
import ScheduleReportModal from "@/components/admin/ScheduleReportModal";

type RevenueSummary = components["schemas"]["RevenueSummary"];
type RevenueTrendPoint = components["schemas"]["RevenueTrendPoint"];
type RevenueByBrandPoint = components["schemas"]["RevenueByBrandPoint"];

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
  // YYYY-MM（月）
  let m = /^\d{4}-(\d{2})$/.exec(period);
  if (m) return `${parseInt(m[1], 10)}月`;
  // YYYY-QN（季）
  m = /^\d{4}-Q(\d)$/.exec(period);
  if (m) return `Q${m[1]}`;
  // YYYY-MM-DD（日 / 週分桶起日）→ M/D
  m = /^\d{4}-(\d{2})-(\d{2})$/.exec(period);
  if (m) return `${parseInt(m[1], 10)}/${parseInt(m[2], 10)}`;
  return period;
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

type Granularity = "day" | "week" | "month" | "quarter";

const SEGMENTS: { label: string; value: Granularity }[] = [
  { label: "日", value: "day" },
  { label: "週", value: "week" },
  { label: "月", value: "month" },
  { label: "季", value: "quarter" },
];

const GRANULARITY_LABEL: Record<Granularity, string> = {
  day: "日",
  week: "週",
  month: "月",
  quarter: "季",
};

// 切換粒度時套用對應預設視窗，避免「日」在近 12 月區間下跑出約 365 根柱。
// 後端 trend 依 date_trunc(granularity) 分桶；此處只決定 range（時間跨度）。
function defaultRangeForGranularity(g: Granularity): DateRange {
  const now = new Date();
  switch (g) {
    case "day":
      return { from: startOfDay(addDays(now, -29)), to: now }; // 近 30 日
    case "week":
      return { from: startOfDay(addDays(now, -83)), to: now }; // 近 12 週
    case "quarter":
      return { from: startOfMonth(addMonths(now, -21)), to: endOfMonth(now) }; // 近 8 季
    case "month":
    default:
      return { from: startOfMonth(addMonths(now, -11)), to: endOfMonth(now) }; // 近 12 月
  }
}

export default function RevenueReportPage() {
  // 粒度 + 日期範圍。trend 依 granularity 真實分桶（後端 date_trunc）；
  // 已接後端 start_date/end_date（reports_v2.get_report_revenue，F-021）。
  const [granularity, setGranularity] = useState<Granularity>("month");
  const [range, setRange] = useState<DateRange>(() =>
    defaultRangeForGranularity("month"),
  );
  const [summary, setSummary] = useState<RevenueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  // 切粒度：同時套用該粒度的預設視窗（batched → 單次 refetch）。
  const handleGranularity = (g: Granularity) => {
    setGranularity(g);
    setRange(defaultRangeForGranularity(g));
  };

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      // v2 tenant-scoped path（FR-0021 / CR-0003 P2-W1）。
      // trend 依 granularity 分桶；start_date/end_date 由 range 導出（both-or-neither）。
      const query: Record<string, string> = { granularity };
      if (range.from && range.to) {
        query.start_date = toDateOnly(range.from);
        query.end_date = toDateOnly(range.to);
      }
      const res = await api.get<RevenueSummary>(
        tenantPath("/reports/revenue"),
        { query },
      );
      setSummary(res);
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
  }, [granularity, range]);

  const rangeLabel = formatDateRange(range);

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
                {updatedLabel}　·　{rangeLabel}（{GRANULARITY_LABEL[granularity]}粒度）
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
            {/* 粒度分段控制：日/週/月/季 → 後端 date_trunc 真實分桶（切換同時套對應預設視窗）。 */}
            <div className="flex rounded-lg bg-[#E2E8F0] p-[3px]">
              {SEGMENTS.map((seg) => (
                <button
                  key={seg.value}
                  onClick={() => handleGranularity(seg.value)}
                  className={`rounded-md px-[14px] py-[6px] text-[13px] ${
                    seg.value === granularity
                      ? "bg-[var(--primary)] font-semibold text-white"
                      : "text-[var(--text-secondary)] hover:bg-white"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <DateRangePicker value={range} onChange={setRange} />

            {/* UAT 隱藏(20260702 決議 7):品牌切片/與上期比較為未實作的即將推出控制 */}
            {!UAT_HIDE_FAKE_FLOWS && (
              <>
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
              </>
            )}

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
              onClick={() => setScheduleOpen(true)}
              className="flex items-center gap-[6px] rounded-lg border border-[#CBD5E1] bg-[var(--bg-page)] px-[14px] py-[7px] hover:bg-white"
            >
              <Calendar className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
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
                <span className="text-xs text-[var(--text-secondary)]">區間營收</span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {formatNtd(kpis?.month_revenue)}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">已開立工單（區間）</span>
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
                  此區間尚無已開立 invoice
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
              {/* UAT 隱藏(20260702 決議 7):未上線功能的預告文字 */}
              {!UAT_HIDE_FAKE_FLOWS && (
                <span className="text-xs text-[var(--text-secondary)]">
                  樞紐切片：時間 × 品牌（待後端 endpoint 擴充後上線）
                </span>
              )}
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
                    營收（區間已開立）
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
          granularity,
          from: range.from ? toDateOnly(range.from) : undefined,
          to: range.to ? toDateOnly(range.to) : undefined,
        }}
      />

      <ScheduleReportModal
        open={scheduleOpen}
        onOpenChange={setScheduleOpen}
        reportType="revenue"
        filters={{
          granularity,
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
