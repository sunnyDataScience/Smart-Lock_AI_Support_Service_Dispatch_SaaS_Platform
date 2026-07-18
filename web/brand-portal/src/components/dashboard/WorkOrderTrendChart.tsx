"use client";

import { useMemo, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

// UAT W6-1：label 走 i18n key（pages.dashboard.charts.ranges）
const RANGES = [
  { key: "7d", days: 7 },
  { key: "14d", days: 14 },
  { key: "30d", days: 30 },
] as const;

type RangeKey = (typeof RANGES)[number]["key"];

interface BucketRow {
  date: string;
  created: number;
  completed: number;
}

interface Props {
  items: WorkOrder[];
  hasMore: boolean;
  loading?: boolean;
  error?: string | null;
  /** 樣本上限提示（顯示「取樣 N 筆」徽章用） */
  sampleLimit: number;
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function shortLabel(key: string): string {
  const [, m, d] = key.split("-");
  return `${parseInt(m, 10)}/${parseInt(d, 10)}`;
}

function buildSeries(items: WorkOrder[], days: number): BucketRow[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const buckets: Record<string, BucketRow> = {};
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = dayKey(d.toISOString());
    buckets[key] = { date: shortLabel(key), created: 0, completed: 0 };
  }

  const earliestKey = Object.keys(buckets)[0];
  for (const wo of items) {
    const ck = dayKey(wo.created_at);
    if (ck >= earliestKey && buckets[ck]) {
      buckets[ck].created += 1;
    }
    if (wo.completion_time) {
      const dk = dayKey(wo.completion_time);
      if (dk >= earliestKey && buckets[dk]) {
        buckets[dk].completed += 1;
      }
    }
  }
  return Object.values(buckets);
}

export default function WorkOrderTrendChart({
  items,
  hasMore,
  loading,
  error,
  sampleLimit,
}: Props) {
  const t = useTranslations("pages.dashboard.charts");
  const [activeRange, setActiveRange] = useState<RangeKey>("14d");

  const days = RANGES.find((r) => r.key === activeRange)?.days ?? 14;
  const data = useMemo(() => buildSeries(items, days), [items, days]);
  const maxValue = useMemo(
    () => data.reduce((m, d) => Math.max(m, d.created, d.completed), 0),
    [data],
  );
  const yMax = useMemo(
    () => Math.max(5, Math.ceil((maxValue + 1) / 5) * 5),
    [maxValue],
  );
  const yTicks = useMemo(
    () => [0, yMax / 5, (yMax / 5) * 2, (yMax / 5) * 3, (yMax / 5) * 4, yMax],
    [yMax],
  );

  return (
    // UAT W6-4：w-[741px] 硬編碼寬 → 響應式（1280 桌面溢出 160px 的主因）
    <div className="flex w-full min-w-0 flex-1 flex-col gap-4 rounded-lg border-[1.5px] border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h3 className="text-[20px] font-semibold text-[var(--text-primary)]">{t("trendTitle")}</h3>
          {hasMore && (
            <span
              className="rounded bg-[var(--badge-warn-bg)] px-2 py-[2px] text-[10px] font-medium text-[var(--badge-warn-fg)]"
              title={t("sampleBadgeTitle", { limit: sampleLimit })}
            >
              {t("sampleBadge", { limit: sampleLimit })}
            </span>
          )}
        </div>
        {/* UAT W6-7：segmented control 白底改 semantic token（深色主題不再亮塊） */}
        <div className="flex gap-0 rounded-lg bg-[var(--bg-page)] p-1">
          {RANGES.map((range) => (
            <button
              key={range.key}
              onClick={() => setActiveRange(range.key)}
              className={`rounded-md px-3 py-[6px] text-[12px] font-medium ${
                activeRange === range.key
                  ? "bg-[var(--primary)] text-white"
                  : "text-[var(--text-secondary)]"
              }`}
            >
              {t(`ranges.${range.key}`)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {t("loadFailed", { error })}
        </div>
      )}

      <div className="h-[240px] w-full">
        {loading && items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[13px] text-[var(--text-secondary)]">
            {t("loading")}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="0" stroke="#F4F4F5" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#A1A1AA" }}
                axisLine={{ stroke: "#E4E4E7" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#A1A1AA" }}
                axisLine={false}
                tickLine={false}
                domain={[0, yMax]}
                ticks={yTicks}
                allowDecimals={false}
              />
              <Tooltip />
              <defs>
                <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563EB" stopOpacity={0.19} />
                  <stop offset="100%" stopColor="#2563EB" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10B981" stopOpacity={0.19} />
                  <stop offset="100%" stopColor="#10B981" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="created"
                stroke="#2563EB"
                strokeWidth={2.5}
                fill="url(#blueGrad)"
                name={t("seriesCreated")}
              />
              <Area
                type="monotone"
                dataKey="completed"
                stroke="#10B981"
                strokeWidth={2.5}
                fill="url(#greenGrad)"
                name={t("seriesCompleted")}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="flex items-center justify-center gap-6">
        <div className="flex items-center gap-[6px]">
          <div className="h-2 w-2 rounded-full bg-[#2563EB]" />
          <span className="text-[13px] font-medium text-[var(--text-secondary)]">{t("seriesCreated")}</span>
        </div>
        <div className="flex items-center gap-[6px]">
          <div className="h-2 w-2 rounded-full bg-[#10B981]" />
          <span className="text-[13px] font-medium text-[var(--text-secondary)]">{t("seriesCompleted")}</span>
        </div>
      </div>
    </div>
  );
}
