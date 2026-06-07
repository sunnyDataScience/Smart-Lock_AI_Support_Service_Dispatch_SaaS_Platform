"use client";

import { useEffect, useState } from "react";
import { FileBarChart, RefreshCw, AlertTriangle, TrendingUp, FileText, CheckCircle2 } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, auth } from "@/lib/api";

type SopMetrics = {
  tenant_id: string;
  window_days: number;
  status_distribution: Record<string, number>;
  totals: { total: number; deleted: number; active: number };
  rates: { approval_rate_pct: number | null; publish_rate_pct: number | null };
  window: { new_drafts: number; newly_published: number };
  top_recent_published: Array<{
    id: string;
    title: string;
    version: number;
    published_at: string | null;
  }>;
  retire_candidates_count: number;
};

const WINDOW_OPTIONS = [
  { label: "7 天", value: 7 },
  { label: "30 天", value: 30 },
  { label: "90 天", value: 90 },
];

function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v.toFixed(1)}%`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  in_review: "審核中",
  approved: "已核准",
  published: "已發布",
  retired: "已停用",
  deleted: "已刪除",
};

export default function SopPerformancePage() {
  const [metrics, setMetrics] = useState<SopMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [windowDays, setWindowDays] = useState(30);

  async function fetchMetrics(days: number) {
    setLoading(true);
    setError(null);
    try {
      const tenantId = auth.getTenantId();
      const res = await api.get<SopMetrics>(
        `/tenants/${encodeURIComponent(tenantId)}/sop-performance/metrics?window_days=${days}`,
      );
      setMetrics(res);
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
  }

  useEffect(() => {
    fetchMetrics(windowDays);
  }, [windowDays]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto pl-14 pr-4 py-6 md:px-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                首頁 &gt; 報表中心 &gt; SOP 績效
              </span>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                SOP 績效
              </h1>
              <span className="text-sm text-[var(--text-secondary)]">
                SOP 知識庫的狀態分佈、核准/發布率、{windowDays} 日內新動態與停用候選
              </span>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex rounded-md border border-[var(--border)] bg-[var(--bg-surface)]">
                {WINDOW_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setWindowDays(opt.value)}
                    className={`px-3 py-1.5 text-[13px] ${
                      windowDays === opt.value
                        ? "bg-[#2563EB] text-white"
                        : "text-[var(--text-secondary)] hover:bg-[#F8FAFC]"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => fetchMetrics(windowDays)}
                disabled={loading}
                className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-[13px] text-[var(--text-secondary)] hover:bg-[#F8FAFC] disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                重新整理
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-md border border-[#FECACA] bg-[#FEF2F2] px-4 py-3">
              <AlertTriangle className="h-4 w-4 text-[#DC2626]" />
              <span className="text-sm text-[#991B1B]">{error}</span>
            </div>
          )}

          {!metrics && !error && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <FileBarChart className="h-12 w-12 text-[var(--text-disabled)]" />
              <span className="text-sm text-[var(--text-secondary)]">
                {loading ? "載入中…" : "尚無資料"}
              </span>
            </div>
          )}

          {metrics && (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                <KpiCard
                  icon={<FileText className="h-5 w-5 text-[#2563EB]" />}
                  label="SOP 總數"
                  value={String(metrics.totals.total)}
                  hint={`啟用中 ${metrics.totals.active} / 已刪除 ${metrics.totals.deleted}`}
                />
                <KpiCard
                  icon={<CheckCircle2 className="h-5 w-5 text-[#059669]" />}
                  label="核准率"
                  value={formatPct(metrics.rates.approval_rate_pct)}
                  hint={`${windowDays} 日累計`}
                />
                <KpiCard
                  icon={<TrendingUp className="h-5 w-5 text-[#7C3AED]" />}
                  label="發布率"
                  value={formatPct(metrics.rates.publish_rate_pct)}
                  hint={`${windowDays} 日累計`}
                />
                <KpiCard
                  icon={<AlertTriangle className="h-5 w-5 text-[#EA580C]" />}
                  label="停用候選"
                  value={String(metrics.retire_candidates_count)}
                  hint={`${windowDays} 日未審查`}
                />
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
                  <h2 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
                    狀態分佈
                  </h2>
                  <div className="flex flex-col gap-2">
                    {Object.keys(metrics.status_distribution).length === 0 && (
                      <span className="text-sm text-[var(--text-secondary)]">尚無資料</span>
                    )}
                    {Object.entries(metrics.status_distribution).map(([status, count]) => {
                      const max = Math.max(...Object.values(metrics.status_distribution), 1);
                      const pct = (count / max) * 100;
                      return (
                        <div key={status} className="flex items-center gap-3">
                          <span className="w-20 shrink-0 text-[13px] text-[var(--text-secondary)]">
                            {STATUS_LABEL[status] ?? status}
                          </span>
                          <div className="flex-1 h-6 overflow-hidden rounded-md bg-[#F1F5F9]">
                            <div
                              className="h-full bg-[#2563EB]"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-12 shrink-0 text-right text-[13px] font-medium text-[var(--text-primary)]">
                            {count}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
                  <h2 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
                    {windowDays} 日內活動
                  </h2>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-lg bg-[#F8FAFC] p-4">
                      <span className="text-[12px] text-[var(--text-secondary)]">新草稿</span>
                      <div className="mt-1 text-2xl font-bold text-[var(--text-primary)]">
                        {metrics.window.new_drafts}
                      </div>
                    </div>
                    <div className="rounded-lg bg-[#F8FAFC] p-4">
                      <span className="text-[12px] text-[var(--text-secondary)]">新發布</span>
                      <div className="mt-1 text-2xl font-bold text-[var(--text-primary)]">
                        {metrics.window.newly_published}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
                <h2 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
                  近期發布 SOP（Top {metrics.top_recent_published.length}）
                </h2>
                {metrics.top_recent_published.length === 0 ? (
                  <span className="text-sm text-[var(--text-secondary)]">尚無資料</span>
                ) : (
                  <div className="overflow-hidden rounded-md border border-[var(--border)]">
                    <div className="flex h-10 items-center border-b border-[var(--border)] bg-[#F8FAFC] px-4 text-[12px] font-semibold text-[var(--text-secondary)]">
                      <span className="flex-1">標題</span>
                      <span className="w-20">版本</span>
                      <span className="w-32">發布日期</span>
                    </div>
                    {metrics.top_recent_published.map((sop) => (
                      <div
                        key={sop.id}
                        className="flex h-12 items-center border-b border-[var(--border)] px-4 text-[13px] last:border-b-0 hover:bg-[#F8FAFC]"
                      >
                        <span className="flex-1 truncate text-[var(--text-primary)]">
                          {sop.title}
                        </span>
                        <span className="w-20 text-[var(--text-secondary)]">
                          v{sop.version}
                        </span>
                        <span className="w-32 text-[var(--text-secondary)]">
                          {formatDate(sop.published_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[13px] text-[var(--text-secondary)]">{label}</span>
      </div>
      <div className="text-2xl font-bold text-[var(--text-primary)]">{value}</div>
      <span className="text-[12px] text-[var(--text-disabled)]">{hint}</span>
    </div>
  );
}
