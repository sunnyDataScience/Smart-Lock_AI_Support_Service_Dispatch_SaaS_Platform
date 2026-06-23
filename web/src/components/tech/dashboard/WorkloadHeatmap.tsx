"use client";

import { Activity } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 後端 GET /technicians/{id}/workload-heatmap 回傳為 untyped dict（A37 端點），
// 此處用 loose type + guard，欄位缺失皆容忍。
interface WorkloadDay {
  date?: string;
  total?: number;
  load_intensity?: string | number;
}
export interface WorkloadData {
  daily?: WorkloadDay[];
  summary?: {
    total_completed?: number;
    completion_rate_pct?: number;
    avg_per_day?: number;
  };
}

interface Props {
  workload: WorkloadData | null;
  loading: boolean;
}

const INTENSITY_COLOR: Record<string, string> = {
  idle: "#F1F5F9",
  low: "#BBF7D0",
  medium: "#FCD34D",
  high: "#FB923C",
  saturated: "#EF4444",
};

function cellColor(day: WorkloadDay): string {
  const li = day.load_intensity;
  if (typeof li === "string" && INTENSITY_COLOR[li]) return INTENSITY_COLOR[li];
  // 數字或缺失：依 total 粗分級
  const n = day.total ?? 0;
  if (n <= 0) return "#F1F5F9";
  if (n <= 1) return "#BBF7D0";
  if (n <= 3) return "#FCD34D";
  if (n <= 5) return "#FB923C";
  return "#EF4444";
}

/**
 * WorkloadHeatmap — 決策屏「本月案量/飽和度」：回答「現在值不值得開工」。
 * 30 日格子熱力圖 + 完成率 + 日均工單。資料來自父層（best-effort，缺則隱藏內容）。
 */
export default function WorkloadHeatmap({ workload, loading }: Props) {
  const t = useTranslations("techPortal.home.workload");

  const daily = workload?.daily ?? [];
  const summary = workload?.summary;
  const completionRate = summary?.completion_rate_pct;
  const avgPerDay = summary?.avg_per_day;

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <Activity className="h-4 w-4 text-[var(--primary)]" />
        <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </h2>
      </div>

      {loading && daily.length === 0 ? (
        <div className="py-4 text-center text-[13px] text-[var(--text-disabled)]">
          {t("loading")}
        </div>
      ) : daily.length === 0 ? (
        <div className="py-4 text-center text-[13px] text-[var(--text-disabled)]">
          {t("empty")}
        </div>
      ) : (
        <>
          <div className="mb-3 flex items-center gap-4 text-[13px]">
            <div className="flex flex-col">
              <span className="text-[18px] font-bold text-[var(--text-primary)]">
                {completionRate != null ? `${Math.round(completionRate)}%` : "—"}
              </span>
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t("completionRate")}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[18px] font-bold text-[var(--text-primary)]">
                {avgPerDay != null ? avgPerDay.toFixed(1) : "—"}
              </span>
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t("avgPerDay")}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-1">
            {daily.map((d, i) => (
              <span
                key={d.date ?? i}
                title={`${d.date ?? ""}${d.total != null ? ` · ${d.total}` : ""}`}
                className="h-4 w-4 rounded-[3px]"
                style={{ backgroundColor: cellColor(d) }}
              />
            ))}
          </div>
          <div className="mt-2 flex items-center justify-end gap-1 text-[10px] text-[var(--text-disabled)]">
            <span>{t("less")}</span>
            {["idle", "low", "medium", "high", "saturated"].map((k) => (
              <span
                key={k}
                className="h-3 w-3 rounded-[2px]"
                style={{ backgroundColor: INTENSITY_COLOR[k] }}
              />
            ))}
            <span>{t("more")}</span>
          </div>
        </>
      )}
    </section>
  );
}
