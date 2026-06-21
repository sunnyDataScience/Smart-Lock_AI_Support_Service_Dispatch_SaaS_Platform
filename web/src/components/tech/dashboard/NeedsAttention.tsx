"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, ChevronRight } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { daysUntilDeadline, type TechStatement } from "@/components/phase-ii";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];

interface Alert {
  key: string;
  level: "warn" | "info";
  text: string;
  href: string;
}

interface Props {
  orders: WorkOrder[];
  statements: TechStatement[];
}

/**
 * NeedsAttention — 決策屏「需注意」：把會出包的事前置（Housecall Pro Needs Attention）。
 * 純前端聚合既有資料：已接未安排工單、對帳單申訴期倒數、申訴處理中。
 */
export default function NeedsAttention({ orders, statements }: Props) {
  const t = useTranslations("techPortal.home.attention");

  const alerts: Alert[] = [];

  // 1) 已接單但尚未安排/出發
  const accepted = orders.filter((o) => o.status === "accepted").length;
  if (accepted > 0) {
    alerts.push({
      key: "accepted",
      level: "warn",
      text: t("acceptedPending", { count: accepted }),
      href: "/my-orders",
    });
  }

  // 2) 對帳單待確認 + 申訴期倒數（取最急者）
  const pendingReview = statements.filter((s) => s.status === "pending_review");
  if (pendingReview.length > 0) {
    const days = pendingReview
      .map((s) => daysUntilDeadline(s.dispute_window_ends_at))
      .filter((d): d is number => d !== null && d >= 0);
    const soonest = days.length > 0 ? Math.min(...days) : null;
    alerts.push({
      key: "statement-pending",
      level: soonest !== null && soonest <= 3 ? "warn" : "info",
      text:
        soonest !== null
          ? t("statementDeadline", { count: pendingReview.length, days: soonest })
          : t("statementPending", { count: pendingReview.length }),
      href: "/account/statements",
    });
  }

  // 3) 申訴處理中
  const disputed = statements.filter((s) => s.status === "disputed").length;
  if (disputed > 0) {
    alerts.push({
      key: "disputed",
      level: "info",
      text: t("disputed", { count: disputed }),
      href: "/account/statements",
    });
  }

  return (
    <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-[#F59E0B]" />
        <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </h2>
      </div>

      {alerts.length === 0 ? (
        <div className="flex items-center gap-2 py-2 text-[13px] text-[var(--text-secondary)]">
          <CheckCircle2 className="h-4 w-4 text-[#10B981]" />
          {t("allClear")}
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {alerts.map((a) => (
            <li key={a.key}>
              <Link
                href={a.href}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-[13px] transition hover:opacity-90 ${
                  a.level === "warn"
                    ? "border-amber-200 bg-amber-50 text-amber-800"
                    : "border-[var(--border)] bg-[var(--bg-page)] text-[var(--text-secondary)]"
                }`}
              >
                <span>{a.text}</span>
                <ChevronRight className="h-4 w-4 shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
