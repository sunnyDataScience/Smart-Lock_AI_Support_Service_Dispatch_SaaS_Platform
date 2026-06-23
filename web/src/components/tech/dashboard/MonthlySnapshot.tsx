"use client";

import { TrendingUp, CheckCircle2, Timer, Star, MessageSquare } from "lucide-react";
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

/**
 * MonthlySnapshot — 月度快照 KPI（CR-0088 P1）：本月毛額（含未結預估）、完成率、
 * 平均到場、客戶評分 + 近期評價。**不顯示租戶內排名**（業主裁決）。
 */
export default function MonthlySnapshot({ summary, loading }: Props) {
  const t = useTranslations("techPortal.home.monthly");

  if (loading && !summary) {
    return (
      <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
        <div className="py-4 text-center text-[13px] text-[var(--text-disabled)]">
          {t("loading")}
        </div>
      </section>
    );
  }

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

  const recent = (s?.recent_feedback ?? []).filter((f) => f.feedback);

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-[var(--primary)]" />
        <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">{t("title")}</h2>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {cells.map(({ key, Icon, value, label }) => (
          <div key={key} className="rounded-lg border border-[var(--border)] p-3">
            <Icon className="h-4 w-4 text-[var(--text-secondary)]" />
            <div className="mt-1 text-[18px] font-bold text-[var(--text-primary)]">{value}</div>
            <div className="text-[11px] text-[var(--text-disabled)]">{label}</div>
          </div>
        ))}
      </div>

      <p className="mt-2 text-[10px] text-[var(--text-disabled)]">{t("estNote")}</p>

      {recent.length > 0 && (
        <div className="mt-3 border-t border-[var(--border)] pt-3">
          <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-[var(--text-secondary)]">
            <MessageSquare className="h-3.5 w-3.5" />
            {t("recentFeedback")}
          </div>
          <ul className="flex flex-col gap-2">
            {recent.map((f, i) => (
              <li key={i} className="rounded-lg bg-[var(--bg-page)] px-3 py-2">
                <div className="flex items-center gap-1 text-[11px] text-amber-500">
                  {f.rating != null
                    ? "★".repeat(f.rating) + "☆".repeat(Math.max(0, 5 - f.rating))
                    : ""}
                </div>
                <p className="mt-0.5 text-[12px] text-[var(--text-primary)] line-clamp-2">
                  {f.feedback}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
