"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const RANGES = [
  { label: "7天", days: 7 },
  { label: "14天", days: 14 },
  { label: "30天", days: 30 },
] as const;

type RangeLabel = (typeof RANGES)[number]["label"];

// API 上限為 100（pydantic Field(le=100)），超過會 422
const FETCH_LIMIT = 100;

interface BucketRow {
  date: string;
  created: number;
  completed: number;
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

export default function WorkOrderTrendChart() {
  const [activeRange, setActiveRange] = useState<RangeLabel>("14天");
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await api.get<WorkOrderPage>("/api/v1/work-orders", {
          query: { limit: FETCH_LIMIT },
        });
        if (cancelled) return;
        setItems(res.items ?? []);
        setHasMore(!!res.has_more);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const days = RANGES.find((r) => r.label === activeRange)?.days ?? 14;
  const data = useMemo(() => buildSeries(items, days), [items, days]);
  const maxValue = useMemo(
    () => data.reduce((m, d) => Math.max(m, d.created, d.completed), 0),
    [data],
  );
  const yMax = Math.max(5, Math.ceil((maxValue + 1) / 5) * 5);
  const yTicks = [0, yMax / 5, (yMax / 5) * 2, (yMax / 5) * 3, (yMax / 5) * 4, yMax];

  return (
    <div className="flex w-[741px] flex-col gap-4 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-[20px] font-semibold text-[#18181B]">工單趨勢</h3>
          {hasMore && (
            <span
              className="rounded bg-[#FEF3C7] px-2 py-[2px] text-[10px] font-medium text-[#B45309]"
              title={`只取最近 ${FETCH_LIMIT} 筆工單；資料量超過時較舊區段可能偏低`}
            >
              取樣 {FETCH_LIMIT} 筆
            </span>
          )}
        </div>
        <div className="flex gap-0 rounded-lg bg-[#F4F4F5] p-1">
          {RANGES.map((range) => (
            <button
              key={range.label}
              onClick={() => setActiveRange(range.label)}
              className={`rounded-md px-3 py-[6px] text-[12px] font-medium ${
                activeRange === range.label
                  ? "bg-[var(--primary)] text-white"
                  : "text-[#71717A]"
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          載入失敗：{error}
        </div>
      )}

      <div className="h-[240px] w-full">
        {loading && items.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[13px] text-[var(--text-secondary)]">
            載入中…
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
                name="新建工單"
              />
              <Area
                type="monotone"
                dataKey="completed"
                stroke="#10B981"
                strokeWidth={2.5}
                fill="url(#greenGrad)"
                name="已完成工單"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="flex items-center justify-center gap-6">
        <div className="flex items-center gap-[6px]">
          <div className="h-2 w-2 rounded-full bg-[#2563EB]" />
          <span className="text-[13px] font-medium text-[#71717A]">新建工單</span>
        </div>
        <div className="flex items-center gap-[6px]">
          <div className="h-2 w-2 rounded-full bg-[#10B981]" />
          <span className="text-[13px] font-medium text-[#71717A]">已完成工單</span>
        </div>
      </div>
    </div>
  );
}
