"use client";

import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { useTranslations } from "@/components/i18n/LocaleProvider";
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

// UAT W6-1：label 走 i18n（pages.dashboard.charts.availability），此處只留色票
const STATUS_COLOR: Record<Availability, string> = {
  available: "#10B981",
  busy: "#2563EB",
  offline: "#A1A1AA",
  on_leave: "#F59E0B",
  circuit_breaker_open: "#EF4444",
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

function bucketByAvailability(
  items: Technician[],
  labelOf: (key: Availability) => string,
): Slice[] {
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
    name: labelOf(key),
    value: counts[key] ?? 0,
    color: STATUS_COLOR[key],
  }));
}

export default function TechnicianStatusChart({ items, loading, error }: Props) {
  const t = useTranslations("pages.dashboard.charts");
  const slices = useMemo(
    () => bucketByAvailability(items, (key) => t(`availability.${key}`)),
    [items, t],
  );
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
    // UAT W6-4：固定寬改響應式——小螢幕滿版、lg 以上固定 371px
    <div className="flex w-full flex-col gap-4 rounded-lg border-[1.5px] border-[var(--border)] bg-[var(--bg-surface)] p-6 lg:w-[371px] lg:shrink-0">
      <h3 className="text-[20px] font-semibold text-[var(--text-primary)]">{t("techStatusTitle")}</h3>

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
          <span className="text-[32px] font-bold leading-none text-[var(--text-primary)]">
            {loading && total === 0 ? "—" : total}
          </span>
          <span className="text-[12px] font-medium text-[var(--text-disabled)]">{t("totalPeople")}</span>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {t("loadFailed", { error })}
        </div>
      )}

      <div className="flex flex-col gap-[10px]">
        {slices.map((item) => (
          <div key={item.key} className="flex items-center gap-2">
            <div
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">
              {item.name}
            </span>
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {t("peopleCount", { count: item.value })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
