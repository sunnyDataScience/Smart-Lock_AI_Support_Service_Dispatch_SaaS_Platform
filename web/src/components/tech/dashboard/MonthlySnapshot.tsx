"use client";

import { TrendingUp, CheckCircle2, Timer, Star } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// 後端 GET /technicians/me/dashboard-summary 回傳（CR-0088）。不含租戶內排名
// （業主 §8-3 裁決不對技師開放）。收入為 estimated_price 預估，非實收。
export interface DashboardSummary {
  today_earnings: number;
  week_earnings: number;
  month_gross_est: number;
  month_completed_earnings: number;
  month_pending_est: number;
  completion_rate_pct: number | null;
  month_total_orders: number;
  month_completed_orders: number;
  today_new_orders: number;
  avg_arrival_minutes: number | null;
  avg_rating: number | null;
  rating_count: number;
  recent_feedback: {
    rating: number | null;
    feedback: string | null;
    completed_at: string | null;
  }[];
}

/** 確定性千分位（避免 toLocaleString 預設 locale 造成 SSR hydration 差異）。 */
export function formatNT(n: number | null | undefined): string {
  if (n == null) return "—";
  return "NT$ " + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

interface Props {
  summary: DashboardSummary | null;
  loading: boolean;
}

// 每格一個語意色（固定 hex + 低透明 tint 底，亮/暗主題皆可讀），
// 取代舊版四格同灰 icon 無層次的呈現。
const CELL_TINT: Record<string, { fg: string; bg: string }> = {
  gross: { fg: "#10B981", bg: "rgba(16,185,129,0.12)" },
  completion: { fg: "#3B82F6", bg: "rgba(59,130,246,0.12)" },
  arrival: { fg: "#F59E0B", bg: "rgba(245,158,11,0.14)" },
  rating: { fg: "#8B5CF6", bg: "rgba(139,92,246,0.12)" },
};

/**
 * MonthlySnapshot — 首頁「本月表現」統計條（CR-0088 P1）：本月毛額（含未結預估）、
 * 完成率、平均到場、客戶評分。**不顯示租戶內排名**（業主裁決）。
 * 近期客戶評價已拆至 RecentFeedback 獨立卡。
 */
export default function MonthlySnapshot({ summary, loading }: Props) {
  const t = useTranslations("techPortal.home.monthly");

  const s = summary;
  const cells = [
    {
      key: "gross",
      Icon: TrendingUp,
      value: formatNT(s?.month_gross_est ?? null),
      label: t("gross"),
    },
    {
      key: "completion",
      Icon: CheckCircle2,
      value: s?.completion_rate_pct != null ? `${Math.round(s.completion_rate_pct)}%` : "—",
      label: t("completion"),
    },
    {
      key: "arrival",
      Icon: Timer,
      value: s?.avg_arrival_minutes != null ? `${Math.round(s.avg_arrival_minutes)}m` : "—",
      label: t("avgArrival"),
    },
    {
      key: "rating",
      Icon: Star,
      value: s?.avg_rating != null ? s.avg_rating.toFixed(1) : "—",
      label: t("rating", { count: s?.rating_count ?? 0 }),
    },
  ];

  return (
    <section aria-label={t("title")}>
      <h2 className="mb-2 px-0.5 text-[13px] font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
        {t("title")}
      </h2>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {cells.map(({ key, Icon, value, label }) => {
          const tint = CELL_TINT[key];
          return (
            <div
              key={key}
              className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-3.5 shadow-sm"
            >
              <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                style={{ backgroundColor: tint.bg, color: tint.fg }}
              >
                <Icon className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <div className="truncate text-[18px] font-bold leading-tight text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                  {loading && !s ? "…" : value}
                </div>
                <div className="truncate text-[11px] text-[var(--text-secondary)]">{label}</div>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-1.5 px-0.5 text-[11px] text-[var(--text-disabled)]">{t("estNote")}</p>
    </section>
  );
}
