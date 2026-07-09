"use client";

import { MessageSquare } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { DashboardSummary } from "./MonthlySnapshot";

interface Props {
  summary: DashboardSummary | null;
}

/**
 * RecentFeedback — 近期客戶評價卡（自 MonthlySnapshot 拆出）。
 * 無任何評價時整卡隱藏（首頁不擺空殼）。
 * CR-0117 S2：星等必填、留言選填 —— 只給星不留言的評價也要顯示（星等即回饋），
 * 先前 filter(f => f.feedback) 會把它們濾光、整卡永遠隱藏。
 */
export default function RecentFeedback({ summary }: Props) {
  const t = useTranslations("techPortal.home.monthly");

  const recent = (summary?.recent_feedback ?? []).filter(
    (f) => f.rating != null || f.feedback,
  );
  if (recent.length === 0) return null;

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
      <div className="mb-3 flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-[var(--primary)]" />
        <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
          {t("recentFeedback")}
        </h2>
      </div>
      <ul className="flex flex-col gap-2">
        {recent.map((f, i) => (
          <li key={i} className="rounded-lg bg-[var(--bg-page)] px-3 py-2">
            <div className="flex items-center gap-1 text-[11px] text-amber-500">
              {f.rating != null
                ? "★".repeat(f.rating) + "☆".repeat(Math.max(0, 5 - f.rating))
                : ""}
            </div>
            {/* star-only 評價無留言 → 不渲染空文字段落 */}
            {f.feedback && (
              <p className="mt-0.5 text-[12px] text-[var(--text-primary)] line-clamp-2">
                {f.feedback}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
