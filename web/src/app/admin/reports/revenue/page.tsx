"use client";

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

const segments = [
  { label: "日", active: false },
  { label: "週", active: false },
  { label: "月", active: true },
  { label: "季", active: false },
];

const chartData = [
  { month: "5月", current: 974300, previous: 780000 },
  { month: "6月", current: 1020000, previous: 820000 },
  { month: "7月", current: 950000, previous: 760000 },
  { month: "8月", current: 1080000, previous: 870000 },
  { month: "9月", current: 920000, previous: 740000 },
  { month: "10月", current: 1050000, previous: 850000 },
  { month: "11月", current: 1100000, previous: 880000 },
  { month: "12月", current: 1150000, previous: 920000 },
  { month: "1月", current: 785500, previous: 650000 },
  { month: "2月", current: 864500, previous: 710000 },
  { month: "3月", current: 871500, previous: 720000 },
  { month: "4月", current: 926200, previous: 760000 },
];

const formatRevenue = (value: number) => {
  if (value === 0) return "0";
  return `${(value / 10000).toFixed(0)}萬`;
};

interface PivotRow {
  month: string;
  yale: string;
  samsung: string;
  gateman: string;
  philips: string;
  others: string;
  total: string;
  isAlt: boolean;
}

const pivotRows: PivotRow[] = [
  { month: "1月", yale: "NT$285,000", samsung: "NT$198,000", gateman: "NT$142,500", philips: "NT$96,800", others: "NT$63,200", total: "NT$785,500", isAlt: false },
  { month: "2月", yale: "NT$312,400", samsung: "NT$215,600", gateman: "NT$156,800", philips: "NT$108,300", others: "NT$71,400", total: "NT$864,500", isAlt: true },
  { month: "3月", yale: "NT$298,700", samsung: "NT$224,100", gateman: "NT$167,300", philips: "NT$112,900", others: "NT$68,500", total: "NT$871,500", isAlt: false },
  { month: "4月", yale: "NT$325,800", samsung: "NT$231,200", gateman: "NT$175,600", philips: "NT$118,400", others: "NT$75,200", total: "NT$926,200", isAlt: true },
  { month: "5月", yale: "NT$341,200", samsung: "NT$245,800", gateman: "NT$183,400", philips: "NT$125,600", others: "NT$78,300", total: "NT$974,300", isAlt: false },
  { month: "6月", yale: "NT$358,600", samsung: "NT$252,400", gateman: "NT$191,700", philips: "NT$132,500", others: "NT$84,800", total: "NT$1,020,000", isAlt: true },
];

const pivotFooter = {
  yale: "NT$1,921,700",
  samsung: "NT$1,367,100",
  gateman: "NT$1,017,300",
  philips: "NT$694,500",
  others: "NT$441,400",
  total: "NT$5,442,000",
};

const pivotColumns = ["月份", "Yale", "Samsung", "Gateman", "Philips", "其他", "總計"];

export default function RevenueReportPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--text-secondary)]">
                首頁 &gt; 報表中心 &gt; 營收
              </span>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                營收報表
              </h1>
              <span className="text-xs text-[var(--text-secondary)]">
                資料截至 2026-04-25 14:30（延遲 &lt; 5 分鐘）
              </span>
            </div>
            <button className="rounded-md p-2">
              <RotateCw className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-3">
            <div className="flex rounded-lg bg-[#E2E8F0] p-[3px]">
              {segments.map((seg) => (
                <button
                  key={seg.label}
                  className={`rounded-md px-[14px] py-[6px] text-[13px] ${
                    seg.active
                      ? "bg-[var(--primary)] font-semibold text-white"
                      : "text-[var(--text-secondary)]"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <button className="flex items-center gap-2 rounded-lg border border-[#CBD5E1] px-3 py-[7px]">
              <Calendar className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
                2025-05 ~ 2026-04
              </span>
            </button>

            <button className="flex items-center gap-2 rounded-lg border border-[#CBD5E1] px-3 py-[7px]">
              <span className="text-[13px] text-[var(--text-primary)]">切片：按品牌</span>
              <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
            </button>

            <div className="flex items-center gap-2">
              <div className="relative h-5 w-9 rounded-full bg-[var(--primary)]">
                <div className="absolute right-[2px] top-[2px] h-4 w-4 rounded-full bg-white" />
              </div>
              <span className="text-[13px] text-[var(--text-primary)]">與上期比較</span>
            </div>

            <div className="flex-1" />

            <button className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-[14px] py-[7px]">
              <Download className="h-[14px] w-[14px] text-white" />
              <span className="text-[13px] font-semibold text-white">匯出</span>
            </button>

            <button className="flex items-center gap-[6px] rounded-lg border border-[#CBD5E1] px-[14px] py-[7px]">
              <Calendar className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">排程發送</span>
            </button>
          </div>

          {/* Revenue Trend Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[#E2E8F0] bg-[var(--bg-surface)] p-6">
            <span className="text-lg font-semibold text-[var(--text-primary)]">
              營收趨勢
            </span>

            {/* Stats Row */}
            <div className="flex gap-6">
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">總營收</span>
                <div className="flex items-center gap-[6px]">
                  <span className="text-xl font-bold text-[var(--text-primary)]">
                    NT$4,821,500
                  </span>
                  <span className="text-xs font-semibold text-[#10B981]">↑12.3%</span>
                </div>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">完工工單</span>
                <span className="text-xl font-bold text-[var(--text-primary)]">489</span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">平均客單</span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  NT$9,861
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-[2px]">
                <span className="text-xs text-[var(--text-secondary)]">成長率</span>
                <span className="text-xl font-bold text-[#10B981]">+12.3%</span>
              </div>
            </div>

            {/* Chart */}
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="0" stroke="#F1F5F9" vertical={false} />
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
                    tickFormatter={formatRevenue}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) => [
                      `NT$ ${value.toLocaleString()}`,
                      name === "current" ? "本期營收" : "上期營收",
                    ]}
                  />
                  <Bar dataKey="previous" fill="#94A3B8" radius={[4, 4, 0, 0]} barSize={16} />
                  <Bar dataKey="current" fill="#2563EB" radius={[4, 4, 0, 0]} barSize={16} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4">
              <div className="flex items-center gap-[6px]">
                <div className="h-3 w-3 rounded-sm bg-[#2563EB]" />
                <span className="text-xs text-[var(--text-secondary)]">本期營收</span>
              </div>
              <div className="flex items-center gap-[6px]">
                <div className="h-3 w-3 rounded-sm bg-[#94A3B8]" />
                <span className="text-xs text-[var(--text-secondary)]">上期營收</span>
              </div>
            </div>
          </div>

          {/* Pivot Table Card */}
          <div className="flex flex-col gap-4 rounded-xl border border-[#E2E8F0] bg-[var(--bg-surface)] p-6">
            <div className="flex items-center">
              <span className="text-lg font-semibold text-[var(--text-primary)]">
                營收樞紐表
              </span>
              <div className="flex-1" />
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <span className="text-xs text-[var(--text-secondary)]">列：</span>
                  <span className="rounded-md border border-[#CBD5E1] px-[10px] py-1 text-xs text-[var(--text-primary)]">
                    時間
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-[var(--text-secondary)]">欄：</span>
                  <span className="rounded-md border border-[#CBD5E1] px-[10px] py-1 text-xs text-[var(--text-primary)]">
                    品牌
                  </span>
                </div>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-hidden rounded-lg border border-[#E2E8F0]">
              {/* Header */}
              <div className="flex bg-[#F1F5F9]">
                {pivotColumns.map((col, i) => (
                  <div
                    key={col}
                    className={`px-3 py-[10px] ${i === 0 ? "w-[100px]" : "flex-1"}`}
                  >
                    <span className={`text-[13px] ${i === 6 ? "font-bold" : "font-semibold"} text-[var(--text-primary)]`}>
                      {col}
                    </span>
                  </div>
                ))}
              </div>

              {/* Data Rows */}
              {pivotRows.map((row) => (
                <div
                  key={row.month}
                  className={`flex ${row.isAlt ? "bg-[var(--bg-page)]" : ""}`}
                >
                  <div className="w-[100px] px-3 py-2">
                    <span className="text-[13px] text-[var(--text-primary)]">{row.month}</span>
                  </div>
                  {[row.yale, row.samsung, row.gateman, row.philips, row.others].map((val, i) => (
                    <div key={i} className="flex-1 px-3 py-2">
                      <span className="text-[13px] text-[var(--text-primary)]">{val}</span>
                    </div>
                  ))}
                  <div className="flex-1 px-3 py-2">
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {row.total}
                    </span>
                  </div>
                </div>
              ))}

              {/* Footer */}
              <div className="flex bg-[#F1F5F9]">
                <div className="w-[100px] px-3 py-[10px]">
                  <span className="text-[13px] font-bold text-[var(--text-primary)]">總計</span>
                </div>
                {[pivotFooter.yale, pivotFooter.samsung, pivotFooter.gateman, pivotFooter.philips, pivotFooter.others].map((val, i) => (
                  <div key={i} className="flex-1 px-3 py-[10px]">
                    <span className="text-[13px] font-bold text-[var(--text-primary)]">
                      {val}
                    </span>
                  </div>
                ))}
                <div className="flex-1 px-3 py-[10px]">
                  <span className="text-[13px] font-bold text-[#2563EB]">
                    {pivotFooter.total}
                  </span>
                </div>
              </div>
            </div>

            {/* Table Footer */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-[var(--text-secondary)]">共 6 列 × 7 欄</span>
              <span className="text-xs text-[var(--text-secondary)]">
                資料截至 2026-04-25 14:30
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
