"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

const data = [
  { name: "品牌 A", value: 35, color: "#2563EB" },
  { name: "品牌 B", value: 30, color: "#F59E0B" },
  { name: "品牌 C", value: 20, color: "#10B981" },
  { name: "品牌 D", value: 15, color: "#8B5CF6" },
];

export default function BrandRevenueChart() {
  return (
    <div className="flex flex-1 flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <span className="text-base font-semibold text-[var(--text-primary)]">
        品牌營收佔比
      </span>

      <div className="flex flex-1 items-center gap-6">
        {/* Donut Chart */}
        <div className="relative h-[180px] w-[180px] flex-shrink-0">
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
              NT$5.2M
            </span>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-3">
          {data.map((item) => (
            <div key={item.name} className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded-[3px]"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-[13px] text-[var(--text-primary)]">
                {item.name}  {item.value}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
