"use client";

import { useEffect, useMemo, useState } from "react";
import { Crown, ChevronDown, Download, RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import DateRangePicker from "@/components/ui/DateRangePicker";
import { getPresetRange, type DateRange } from "@/lib/dateRange";
import { ApiError, api, tenantPath } from "@/lib/api";
import type { components } from "@/types/api.generated";
import { ReportExportModal } from "@/components/admin/reports/ReportExportModal";

type Technician = components["schemas"]["Technician"];
type TechnicianPage = components["schemas"]["TechnicianPage"];

const SEGMENTS = [
  { label: "本週", value: "week" },
  { label: "本月", value: "month" },
  { label: "本季", value: "quarter" },
  { label: "本年", value: "year" },
] as const;

type SortKey = "composite" | "rating" | "completed";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "composite", label: "排序：綜合評分" },
  { value: "rating", label: "排序：平均星等" },
  { value: "completed", label: "排序：完工數" },
];

const AVATAR_PALETTE = [
  "#DBEAFE",
  "#E0E7FF",
  "#FEF3C7",
  "#FCE7F3",
  "#D1FAE5",
  "#FEE2E2",
  "#EDE9FE",
  "#CFFAFE",
];

function avatarBg(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) & 0xffffffff;
  }
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function compositeScore(t: Technician): number {
  return Math.round((t.rating ?? 0) * 20 * 10) / 10;
}

function sortTechnicians(items: Technician[], sortKey: SortKey = "composite"): Technician[] {
  return [...items].sort((a, b) => {
    if (sortKey === "rating") return (b.rating ?? 0) - (a.rating ?? 0);
    if (sortKey === "completed")
      return (b.completed_orders_count ?? 0) - (a.completed_orders_count ?? 0);
    // composite: rating tiebreak by completed
    const ra = a.rating ?? 0;
    const rb = b.rating ?? 0;
    if (rb !== ra) return rb - ra;
    return (b.completed_orders_count ?? 0) - (a.completed_orders_count ?? 0);
  });
}

const availabilityLabel: Record<Technician["availability"], { label: string; color: string; bg: string }> = {
  available: { label: "可派工", color: "#15803D", bg: "#DCFCE7" },
  busy: { label: "執行中", color: "#1D4ED8", bg: "#DBEAFE" },
  offline: { label: "離線", color: "#475569", bg: "#E2E8F0" },
  on_leave: { label: "請假", color: "#92400E", bg: "#FEF3C7" },
  circuit_breaker_open: { label: "熔斷中", color: "#B91C1C", bg: "#FEE2E2" },
};

const levelLabel: Record<string, { label: string; color: string; bg: string }> = {
  A: { label: "A 級", color: "#1D4ED8", bg: "#DBEAFE" },
  B: { label: "B 級", color: "#15803D", bg: "#DCFCE7" },
  C: { label: "C 級", color: "#92400E", bg: "#FEF3C7" },
};

const columns = [
  { label: "排名", width: "w-[60px]" },
  { label: "技師", width: "w-[180px]" },
  { label: "等級", width: "w-[80px]" },
  { label: "可用狀態", width: "w-[100px]" },
  { label: "完工工單", width: "w-[90px]" },
  { label: "平均星等", width: "w-[100px]" },
  { label: "綜合評分", width: "w-[120px]" },
  { label: "服務區域", width: "flex-1" },
];

function PodiumBadge({ rank, color }: { rank: number; color: string }) {
  const bgMap: Record<number, string> = { 2: "#F1F5F9", 3: "#FFF7ED" };
  return (
    <div
      className="rounded-xl px-3 py-1"
      style={{ backgroundColor: bgMap[rank] }}
    >
      <span className="text-xs font-semibold" style={{ color }}>
        #{rank}
      </span>
    </div>
  );
}

interface PodiumDecor {
  scoreColor: string;
  borderColor: string;
}

const podiumDecor: Record<number, PodiumDecor> = {
  1: { scoreColor: "#FBBF24", borderColor: "#FBBF24" },
  2: { scoreColor: "#64748B", borderColor: "#94A3B8" },
  3: { scoreColor: "#D97706", borderColor: "#D97706" },
};

export default function TechnicianRankingPage() {
  // 日期範圍 — 預設「本月」（與 segments 內被選中的「本月」一致）。
  // TODO[E7x §4.3]: /tenants/{tid}/technicians 尚無 date filter，
  // range state 暫時只控制 UI；技師排名仍以全 100 筆 sample 計算。
  const [range, setRange] = useState<DateRange>(() => getPresetRange("thisMonth"));
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [period, setPeriod] = useState<"week" | "month" | "quarter" | "year">("month");
  const [sortKey, setSortKey] = useState<SortKey>("composite");
  const [regionFilter, setRegionFilter] = useState<string>("");
  const [pageIndex, setPageIndex] = useState(0);

  const PAGE_SIZE = 25;

  const fetchTechnicians = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<TechnicianPage>(
        tenantPath("/technicians"),
        { query: { limit: 100 } },
      );
      const items: Technician[] = res.items ?? [];
      setTechnicians(items);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTechnicians();
  }, []);

  const allDisplayed = useMemo(() => {
    const filtered = regionFilter
      ? technicians.filter((t) => (t.service_areas ?? []).includes(regionFilter))
      : technicians;
    return sortTechnicians(filtered, sortKey);
  }, [technicians, regionFilter, sortKey]);

  const totalPages = Math.max(1, Math.ceil(allDisplayed.length / PAGE_SIZE));
  const safePage = Math.min(pageIndex, totalPages - 1);
  const displayedTechnicians = useMemo(
    () => allDisplayed.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE),
    [allDisplayed, safePage],
  );

  const podium = allDisplayed.slice(0, 3);
  const updatedLabel = updatedAt
    ? `資料更新於 ${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
    : "尚未載入";

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex flex-col gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 報表 &gt; 技師排行
            </span>
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
                技師排行榜
              </h1>
              <div className="flex items-center gap-3">
                <span className="text-xs text-[var(--text-secondary)]">
                  {updatedLabel}
                </span>
                <button
                  onClick={fetchTechnicians}
                  disabled={loading}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                  title="重新整理"
                >
                  <RefreshCw
                    className={`h-4 w-4 text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
                  />
                </button>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入技師列表失敗：{error}
            </div>
          )}

          <div className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
            <div className="flex rounded-lg bg-[#F1F5F9] p-[3px]">
              {SEGMENTS.map((seg) => (
                <button
                  key={seg.value}
                  onClick={() => setPeriod(seg.value)}
                  className={`rounded-md px-[14px] py-[6px] text-[13px] ${
                    seg.value === period
                      ? "bg-[var(--primary)] font-semibold text-white"
                      : "font-medium text-[var(--text-secondary)] hover:bg-white"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <DateRangePicker value={range} onChange={setRange} />

            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            <select
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value)}
              className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
            >
              <option value="">全部區域</option>
              {Array.from(new Set(technicians.flatMap((t) => t.service_areas ?? []))).sort().map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>

            <div className="flex-1" />

            <button
              onClick={() => setExportOpen(true)}
              title="匯出 CSV"
              className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 hover:bg-[var(--bg-page)]"
            >
              <Download className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
                匯出 CSV
              </span>
            </button>
          </div>

          <div className="flex gap-4">
            {loading && podium.length === 0 ? (
              <div className="flex h-[260px] flex-1 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] text-sm text-[var(--text-secondary)]">
                載入中…
              </div>
            ) : podium.length === 0 ? (
              <div className="flex h-[260px] flex-1 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] text-sm text-[var(--text-secondary)]">
                目前沒有技師資料
              </div>
            ) : (
              podium.map((t, idx) => {
                const rank = idx + 1;
                const decor = podiumDecor[rank];
                const score = compositeScore(t);
                return (
                  <div
                    key={t.id}
                    className="flex flex-1 flex-col items-center gap-3 rounded-xl bg-[var(--bg-surface)] p-6"
                    style={{ border: `2px solid ${decor.borderColor}` }}
                  >
                    {rank === 1 ? (
                      <Crown className="h-7 w-7 text-[#FBBF24]" />
                    ) : (
                      <PodiumBadge rank={rank} color={decor.borderColor} />
                    )}

                    <div
                      className="flex h-20 w-20 items-center justify-center rounded-full text-2xl font-bold text-[var(--text-primary)]"
                      style={{ backgroundColor: avatarBg(t.name) }}
                    >
                      {t.name[0] ?? "?"}
                    </div>

                    <span className="text-base font-semibold text-[var(--text-primary)]">
                      {t.name}
                    </span>

                    <span
                      className="text-[32px] font-bold leading-none"
                      style={{ color: decor.scoreColor }}
                    >
                      {score.toFixed(1)}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)]">
                      綜合評分（rating × 20）
                    </span>

                    <div className="flex w-full items-center justify-around">
                      <div className="flex flex-col items-center gap-[2px]">
                        <span className="text-sm font-semibold text-[#3B82F6]">
                          {t.completed_orders_count ?? 0}
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)]">
                          完工工單
                        </span>
                      </div>
                      <div className="flex flex-col items-center gap-[2px]">
                        <span className="text-sm font-semibold text-[#F59E0B]">
                          {t.rating?.toFixed(1) ?? "—"} ★
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)]">
                          評分
                        </span>
                      </div>
                      <div className="flex flex-col items-center gap-[2px]">
                        <span className="text-sm font-semibold text-[var(--text-primary)]">
                          {t.level}
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)]">
                          等級
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center rounded-t-xl bg-[#F8FAFC] px-4 py-3">
              {columns.map((col) => (
                <div key={col.label} className={`${col.width} shrink-0`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {loading && technicians.length === 0 && (
              <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
                載入中…
              </div>
            )}
            {!loading && technicians.length === 0 && (
              <div className="flex h-[120px] items-center justify-center text-sm text-[var(--text-secondary)]">
                目前沒有技師資料
              </div>
            )}

            {displayedTechnicians.map((t, idx) => {
              const rank = idx + 1;
              const score = compositeScore(t);
              const avail = availabilityLabel[t.availability] ?? availabilityLabel.offline;
              const lvl = levelLabel[t.level] ?? { label: t.level, color: "#475569", bg: "#F1F5F9" };
              const areas = (t.service_areas ?? []).join("、") || "—";

              return (
                <div
                  key={t.id}
                  className="flex items-center border-b border-[var(--border)] px-4 py-[10px] last:border-b-0"
                >
                  <div className="w-[60px] shrink-0">
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {rank}
                    </span>
                  </div>

                  <div className="flex w-[180px] shrink-0 items-center gap-2">
                    <div
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-[var(--text-primary)]"
                      style={{ backgroundColor: avatarBg(t.name) }}
                    >
                      {t.name[0] ?? "?"}
                    </div>
                    <span className="truncate text-[13px] text-[var(--text-primary)]">
                      {t.name}
                    </span>
                  </div>

                  <div className="w-[80px] shrink-0">
                    <span
                      className="rounded-md px-2 py-[2px] text-[11px] font-semibold"
                      style={{ backgroundColor: lvl.bg, color: lvl.color }}
                    >
                      {lvl.label}
                    </span>
                  </div>

                  <div className="w-[100px] shrink-0">
                    <span
                      className="rounded-md px-2 py-[2px] text-[11px] font-semibold"
                      style={{ backgroundColor: avail.bg, color: avail.color }}
                    >
                      {avail.label}
                    </span>
                  </div>

                  <div className="w-[90px] shrink-0">
                    <span className="text-[13px] text-[var(--text-primary)]">
                      {t.completed_orders_count ?? 0}
                    </span>
                  </div>

                  <div className="w-[100px] shrink-0">
                    <span className="text-[13px] text-[#F59E0B]">
                      {t.rating?.toFixed(1) ?? "—"} ★
                    </span>
                  </div>

                  <div className="flex w-[120px] shrink-0 items-center gap-2">
                    <div className="h-2 w-[60px] rounded bg-[#F1F5F9]">
                      <div
                        className="h-2 rounded bg-[#2563EB]"
                        style={{ width: `${Math.min(100, score)}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-[var(--text-primary)]">
                      {score.toFixed(1)}
                    </span>
                  </div>

                  <div className="min-w-0 flex-1">
                    <span
                      className="truncate text-[13px] text-[var(--text-secondary)]"
                      title={areas}
                    >
                      {areas}
                    </span>
                  </div>
                </div>
              );
            })}

            <div className="flex items-center justify-between px-4 py-3">
              <span className="text-[13px] text-[var(--text-secondary)]">
                顯示 {allDisplayed.length} 位技師（第 {safePage + 1}/{totalPages} 頁）
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPageIndex(Math.max(0, safePage - 1))}
                  disabled={safePage === 0}
                  className="rounded-md border border-[var(--border)] px-[10px] py-[6px] text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  上一頁
                </button>
                <span className="rounded-md bg-[var(--primary)] px-[10px] py-[6px] text-xs font-semibold text-white">
                  {safePage + 1}
                </span>
                <button
                  onClick={() => setPageIndex(Math.min(totalPages - 1, safePage + 1))}
                  disabled={safePage >= totalPages - 1}
                  className="rounded-md border border-[var(--border)] px-[10px] py-[6px] text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  下一頁
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ReportExportModal
        open={exportOpen}
        onOpenChange={setExportOpen}
        reportType="technician_ranking"
        filters={{
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
