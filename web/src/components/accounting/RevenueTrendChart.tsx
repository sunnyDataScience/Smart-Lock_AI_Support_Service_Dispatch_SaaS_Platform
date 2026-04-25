"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Line,
  ComposedChart,
} from "recharts";

const data = [
  { month: "1月", revenue: 1300000, orders: 280 },
  { month: "2月", revenue: 1550000, orders: 320 },
  { month: "3月", revenue: 1200000, orders: 260 },
  { month: "4月", revenue: 1750000, orders: 380 },
  { month: "5月", revenue: 950000, orders: 210 },
  { month: "6月", revenue: 1400000, orders: 310 },
  { month: "7月", revenue: 1600000, orders: 350 },
  { month: "8月", revenue: 1850000, orders: 410 },
  { month: "9月", revenue: 1450000, orders: 320 },
  { month: "10月", revenue: 1700000, orders: 370 },
  { month: "11月", revenue: 1950000, orders: 430 },
  { month: "12月", revenue: 2100000, orders: 470 },
];

const formatRevenue = (value: number) => {
  if (value === 0) return "0";
  return `${value / 10000}萬`;
};

export default function RevenueTrendChart() {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      {/* Chart Header */}
      <div className="flex items-center justify-between">
        <span className="text-base font-semibold text-[var(--text-primary)]">
          營收趨勢
        </span>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-[6px]">
            <div className="h-3 w-3 rounded-[3px] bg-[var(--primary)]" />
            <span className="text-xs text-[var(--text-secondary)]">營收金額</span>
          </div>
          <div className="flex items-center gap-[6px]">
            <div className="h-3 w-3 rounded-[3px] bg-[#F59E0B]" />
            <span className="text-xs text-[var(--text-secondary)]">工單數量</span>
          </div>
        </div>
      </div>

      {/* Chart Body */}
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 0, right: 50, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="0" stroke="#F1F5F9" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 11, fill: "#64748B" }}
              axisLine={{ stroke: "#E2E8F0" }}
              tickLine={false}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: "#64748B" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={formatRevenue}
              domain={[0, 2000000]}
              ticks={[0, 500000, 1000000, 1500000, 2000000]}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: "#F59E0B" }}
              axisLine={false}
              tickLine={false}
              domain={[0, 500]}
              ticks={[100, 200, 300, 400, 500]}
            />
            <Tooltip
              formatter={(value: number, name: string) => {
                if (name === "revenue") return [`NT$ ${value.toLocaleString()}`, "營收金額"];
                return [value, "工單數量"];
              }}
            />
            <Bar
              yAxisId="left"
              dataKey="revenue"
              fill="#2563EB"
              radius={[4, 4, 0, 0]}
              barSize={40}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="orders"
              stroke="#F59E0B"
              strokeWidth={3}
              dot={false}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
