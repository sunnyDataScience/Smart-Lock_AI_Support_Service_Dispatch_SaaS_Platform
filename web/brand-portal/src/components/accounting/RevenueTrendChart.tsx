"use client";

import { useMemo } from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Bar,
  Line,
  ComposedChart,
} from "recharts";
import type { components } from "@/types/api.generated";

type RevenueTrendPoint = components["schemas"]["RevenueTrendPoint"];

interface Props {
  items: RevenueTrendPoint[];
  loading?: boolean;
}

const formatRevenue = (value: number) => {
  if (value === 0) return "0";
  if (value >= 10000) return `${Math.round(value / 1000) / 10}萬`;
  return `${value}`;
};

function periodLabel(period: string): string {
  const m = /^\d{4}-(\d{2})$/.exec(period);
  return m ? `${parseInt(m[1], 10)}月` : period;
}

export default function RevenueTrendChart({ items, loading }: Props) {
  const data = useMemo(
    () =>
      items.map((p) => ({
        month: periodLabel(p.period),
        revenue: Number(p.revenue),
        orders: p.order_count,
      })),
    [items],
  );

  const yMax = useMemo(() => {
    const maxRevenue = data.reduce((acc, d) => Math.max(acc, d.revenue), 0);
    return maxRevenue > 0 ? Math.ceil((maxRevenue * 1.2) / 10000) * 10000 : 100000;
  }, [data]);

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <span className="text-base font-semibold text-[var(--text-primary)]">
          營收趨勢（近 12 個月）
        </span>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-[6px]">
            <div className="h-3 w-3 rounded-[3px] bg-[var(--primary)]" />
            <span className="text-xs text-[var(--text-secondary)]">營收金額</span>
          </div>
          <div className="flex items-center gap-[6px]">
            <div className="h-3 w-3 rounded-[3px] bg-[#F59E0B]" />
            <span className="text-xs text-[var(--text-secondary)]">發票數量</span>
          </div>
        </div>
      </div>

      <div className="h-[260px] w-full">
        {loading && data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-secondary)]">
            載入中…
          </div>
        ) : data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-secondary)]">
            尚無營收資料
          </div>
        ) : (
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
                domain={[0, yMax]}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 11, fill: "#F59E0B" }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip
                formatter={(value: number, name: string) => {
                  if (name === "revenue") return [`NT$ ${value.toLocaleString()}`, "營收金額"];
                  return [value, "發票數量"];
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
        )}
      </div>
    </div>
  );
}
