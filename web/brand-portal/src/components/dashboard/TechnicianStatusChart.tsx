"use client";

import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type Availability = Technician["availability"];

const STATUS_ORDER: Availability[] = [
  "available",
  "busy",
  "offline",
  "on_leave",
  "circuit_breaker_open",
];

const STATUS_META: Record<Availability, { name: string; color: string }> = {
  available: { name: "可用", color: "#10B981" },
  busy: { name: "外出中", color: "#2563EB" },
  offline: { name: "離線", color: "#A1A1AA" },
  on_leave: { name: "休假中", color: "#F59E0B" },
  circuit_breaker_open: { name: "熔斷中", color: "#EF4444" },
};

interface Slice {
  key: Availability;
  name: string;
  value: number;
  color: string;
}

interface Props {
  items: Technician[];
  loading?: boolean;
  error?: string | null;
}

function bucketByAvailability(items: Technician[]): Slice[] {
  const counts: Record<Availability, number> = {
    available: 0,
    busy: 0,
    offline: 0,
    on_leave: 0,
    circuit_breaker_open: 0,
  };
  for (const t of items) {
    counts[t.availability] = (counts[t.availability] ?? 0) + 1;
  }
  return STATUS_ORDER.map((key) => ({
    key,
    name: STATUS_META[key].name,
    value: counts[key] ?? 0,
    color: STATUS_META[key].color,
  }));
}

export default function TechnicianStatusChart({ items, loading, error }: Props) {
  const slices = useMemo(() => bucketByAvailability(items), [items]);
  const total = useMemo(
    () => slices.reduce((sum, d) => sum + d.value, 0),
    [slices],
  );
  const chartData = useMemo(() => {
    const visible = slices.filter((s) => s.value > 0);
    return visible.length > 0
      ? visible
      : [
          {
            name: "—",
            value: 1,
            color: "#E4E4E7",
            key: "available" as Availability,
          },
        ];
  }, [slices]);

  return (
    <div className="flex w-[371px] flex-col gap-4 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-6">
      <h3 className="text-[20px] font-semibold text-[#18181B]">技師狀態分佈</h3>

      <div className="relative mx-auto h-[168px] w-[168px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={80}
              startAngle={90}
              endAngle={-270}
              paddingAngle={0}
              dataKey="value"
              stroke="none"
            >
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[32px] font-bold leading-none text-[#18181B]">
            {loading && total === 0 ? "—" : total}
          </span>
          <span className="text-[12px] font-medium text-[#A1A1AA]">總人數</span>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          載入失敗：{error}
        </div>
      )}

      <div className="flex flex-col gap-[10px]">
        {slices.map((item) => (
          <div key={item.key} className="flex items-center gap-2">
            <div
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[13px] font-medium text-[#71717A]">
              {item.name}
            </span>
            <span className="text-[13px] font-semibold text-[#18181B]">
              {item.value}人
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
