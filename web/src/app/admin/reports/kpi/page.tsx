"use client";

import { useEffect, useState } from "react";
import {
  RefreshCw,
  Calendar,
  ChevronDown,
  Download,
  Timer,
  Info,
  ArrowRight,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type KpiReport = components["schemas"]["KpiReport"];
type Period = components["schemas"]["DashboardPeriod"];

const SEGMENTS: { label: string; value: Period }[] = [
  { label: "今日", value: "today" },
  { label: "7 天", value: "7d" },
  { label: "30 天", value: "30d" },
  { label: "90 天", value: "90d" },
];

function formatPercent(rateStr: string | null | undefined): string {
  if (rateStr === null || rateStr === undefined) return "—";
  const v = Number(rateStr);
  if (!Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function formatGeneratedAt(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

interface FunnelStage {
  label: string;
  value: number;
  color: string;
}

function buildFunnel(report: KpiReport | null): FunnelStage[] {
  const f = report?.funnel;
  if (!f) return [];
  return [
    { label: "對話建立", value: f.conversations, color: "#1E40AF" },
    { label: "ProblemCard 產出", value: f.problem_cards, color: "#2563EB" },
    { label: "工單建立", value: f.work_orders, color: "#3B82F6" },
    { label: "派出/接受", value: f.dispatched, color: "#06B6D4" },
    { label: "完工", value: f.completed, color: "#10B981" },
  ];
}

function PendingTag({ note }: { note: string }) {
  return (
    <span
      className="ml-2 rounded-md bg-[#FEF3C7] px-2 py-[2px] text-[10px] font-semibold text-[#92400E]"
      title={note}
    >
      待接入
    </span>
  );
}

export default function KpiDashboardPage() {
  const [period, setPeriod] = useState<Period>("30d");
  const [report, setReport] = useState<KpiReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function fetchReport(p: Period) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<KpiReport>(
        `/api/v1/reports/kpi?period=${p}`,
      );
      setReport(res);
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
    fetchReport(period);
  }, [period]);

  const funnel = buildFunnel(report);
  const baseValue = funnel[0]?.value ?? 0;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {/* Page Header */}
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 報表 &gt; KPI 儀表板
            </span>
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
                KPI 儀表板
              </h1>
              <button
                onClick={() => fetchReport(period)}
                disabled={loading}
                title="重新整理"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
            </div>
            <span className="text-[13px] text-[var(--text-secondary)]">
              資料截至 {formatGeneratedAt(report?.generated_at)}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-relaxed text-amber-800">
            目前僅展示可從現有資料表計算的 KPI（轉換漏斗 / 異常率 / 平均處理時長）；
            SLA 達成率 / 客戶滿意度 / NPS / 差評率 / FTFR 等指標需各自獨立模組接入後再上線。
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-3">
            <div className="flex rounded-lg bg-[#F1F5F9] p-[3px]">
              {SEGMENTS.map((seg) => (
                <button
                  key={seg.value}
                  onClick={() => setPeriod(seg.value)}
                  className={`rounded-md px-[14px] py-[6px] text-[13px] ${
                    period === seg.value
                      ? "bg-[var(--primary)] font-medium text-white"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <button
              disabled
              title="即將推出（自訂日期區間）"
              className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-[7px] opacity-50"
            >
              <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
                自訂日期區間
              </span>
            </button>

            <button
              disabled
              title="即將推出（品牌 / 區域切片）"
              className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-[7px] opacity-50"
            >
              <span className="text-[13px] text-[var(--text-primary)]">切片：全部</span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>

            <div className="flex-1" />

            <button
              disabled
              title="即將推出"
              className="flex cursor-not-allowed items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-[7px] opacity-50"
            >
              <Download className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">匯出報告</span>
            </button>

            <button
              disabled
              title="即將推出（排程週/月報）"
              className="flex cursor-not-allowed items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-[7px] opacity-50"
            >
              <Timer className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">排程週/月報</span>
            </button>
          </div>

          {/* Conversion Funnel Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-[var(--text-primary)]">
                轉換漏斗
              </span>
              <Info className="h-4 w-4 text-[var(--text-disabled)]" />
            </div>

            {loading && !report ? (
              <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                載入中…
              </div>
            ) : baseValue === 0 ? (
              <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                此期間尚無對話資料
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-2">
                  {funnel.map((row) => {
                    const widthPercent =
                      baseValue > 0
                        ? Math.max(15, (row.value / baseValue) * 100)
                        : 100;
                    const ratio =
                      baseValue > 0
                        ? `${((row.value / baseValue) * 100).toFixed(1)}%`
                        : "—";
                    return (
                      <div
                        key={row.label}
                        className="flex h-9 items-center justify-between rounded-md px-3"
                        style={{
                          backgroundColor: row.color,
                          width: `${widthPercent}%`,
                        }}
                      >
                        <span className="text-xs font-semibold text-white">
                          {row.label}
                        </span>
                        <span className="text-xs font-semibold text-white">
                          {row.value.toLocaleString()}（{ratio}）
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Stage-to-stage rate */}
                <div className="flex items-center justify-center gap-[6px] pt-2">
                  {funnel.slice(1).map((row, i) => {
                    const prev = funnel[i].value;
                    const rate =
                      prev > 0
                        ? `${((row.value / prev) * 100).toFixed(1)}%`
                        : "—";
                    const color = prev > 0 && row.value / prev >= 0.9
                      ? "#10B981"
                      : "#2563EB";
                    return (
                      <div key={i} className="flex items-center gap-[6px]">
                        {i > 0 && (
                          <ArrowRight className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
                        )}
                        <span
                          className="text-[11px] font-semibold"
                          style={{ color }}
                        >
                          {rate}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <span className="text-center text-[11px] text-[var(--text-secondary)]">
                  各階段轉換率
                </span>
              </>
            )}
          </div>

          {/* Dispute & Anomaly Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              異常率
            </span>
            <div className="flex gap-4">
              <DisputeRow
                label="退款率"
                rate={report?.dispute_rates?.refund_rate}
                target={0.05}
                hint="refund_requests / work_orders"
              />
              <DisputeRow
                label="保固索賠率"
                rate={report?.dispute_rates?.warranty_claim_rate}
                target={0.05}
                hint="warranty_claims / work_orders"
              />
              <DisputeRow
                label="爭議升級率"
                rate={report?.dispute_rates?.dispute_rate}
                target={0.02}
                hint="disputes / work_orders"
              />
            </div>
          </div>

          {/* Technician Efficiency Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              技師效率
            </span>

            <div className="flex gap-4">
              <div className="flex flex-1 flex-col items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  平均處理時長
                </span>
                <span className="text-2xl font-bold text-[var(--text-primary)]">
                  {report?.technician_efficiency?.avg_handle_minutes != null
                    ? `${report.technician_efficiency.avg_handle_minutes} 分`
                    : "—"}
                </span>
                <span className="text-[11px] text-[var(--text-secondary)]">
                  樣本：{report?.technician_efficiency?.completed_count ?? 0} 筆完工
                </span>
              </div>
              <div className="flex flex-1 flex-col items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <div className="flex items-center text-[13px] text-[var(--text-secondary)]">
                  一次修好率（FTFR）
                  <PendingTag note="需 rework_of_id 業務邏輯確認" />
                </div>
                <span className="text-2xl font-bold text-[var(--text-disabled)]">—</span>
                <span className="text-[11px] text-[var(--text-secondary)]">尚未接入</span>
              </div>
            </div>
          </div>

          {/* SLA placeholder */}
          <div className="flex flex-col gap-3 rounded-xl border border-dashed border-[var(--border)] bg-[#F8FAFC] p-6">
            <div className="flex items-center">
              <span className="text-base font-semibold text-[var(--text-secondary)]">
                SLA 達成率 / 客戶滿意度 / NPS / 差評率
              </span>
              <PendingTag note="需 SLA 規則表 + 評價回傳機制" />
            </div>
            <span className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
              {report?.notes?.length
                ? report.notes.join("；")
                : "需各自獨立模組接入後再上線。"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DisputeRow({
  label,
  rate,
  target,
  hint,
}: {
  label: string;
  rate: string | null | undefined;
  target: number;
  hint: string;
}) {
  const v = rate ? Number(rate) : null;
  const pct = v !== null && Number.isFinite(v) ? v * 100 : null;
  const color =
    pct === null
      ? "#94A3B8"
      : v! > target
        ? "var(--status-warning)"
        : "var(--status-success)";
  const barWidth = pct === null ? 0 : Math.min(100, pct * 5);

  return (
    <div className="flex flex-1 flex-col gap-3 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-[var(--text-primary)]">{label}</span>
        <span
          className="text-[13px] font-semibold"
          style={{ color }}
        >
          {formatPercent(rate)}
        </span>
      </div>
      <div className="h-2 w-full rounded bg-[#E2E8F0]">
        <div
          className="h-2 rounded transition-all"
          style={{
            width: `${barWidth}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <span className="text-[11px] text-[var(--text-secondary)]">{hint}</span>
    </div>
  );
}
