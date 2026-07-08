"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import type { components } from "@shared/types/api.generated";

type RevenueByBrandPoint = components["schemas"]["RevenueByBrandPoint"];

interface Props {
  items: RevenueByBrandPoint[];
  loading?: boolean;
}

const PALETTE = ["#2563EB", "#F59E0B", "#10B981", "#8B5CF6", "#EC4899", "#06B6D4"];

function formatTotal(amount: number): string {
  if (amount >= 1_000_000) return `NT$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `NT$${(amount / 1_000).toFixed(0)}K`;
  return `NT$${amount.toLocaleString()}`;
}

export default function BrandRevenueChart({ items, loading }: Props) {
  const data = items.map((p, i) => ({
    name: p.brand,
    value: Number(p.revenue),
    sharePct: Math.round(p.share * 100),
    color: PALETTE[i % PALETTE.length],
  }));

  const total = data.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="flex flex-1 flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <span className="text-base font-semibold text-[var(--text-primary)]">
        品牌營收佔比
      </span>

      <div className="flex flex-1 items-center gap-6">
        <div className="relative h-[180px] w-[180px] flex-shrink-0">
          {loading && data.length === 0 ? (
            <div className="flex h-full items-center justify-center text-[12px] text-[var(--text-secondary)]">
              載入中…
            </div>
          ) : data.length === 0 ? (
            <div className="flex h-full items-center justify-center text-center text-[12px] text-[var(--text-secondary)]">
              尚無資料
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data}
                    cx="50%"
                    cy="50%"
                    innerRadius={58}
                    outerRadius={90}
                    startAngle={90}
                    endAngle={-270}
                    paddingAngle={0}
                    dataKey="value"
                    stroke="none"
                  >
                    {data.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[11px] text-[var(--text-secondary)]">總營收</span>
                <span className="text-base font-bold text-[var(--text-primary)]">
                  {formatTotal(total)}
                </span>
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col gap-3">
          {data.map((item) => (
            <div key={item.name} className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded-[3px]"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-[13px] text-[var(--text-primary)]">
                {item.name}　{item.sharePct}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
