"use client";

import { Calendar, ChevronDown, Search } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ProblemCardsTable from "@/components/problem-cards/ProblemCardsTable";
import { ApiError } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];

function formatProblemCardError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const PAGE_SIZE = 20;

const FILTER_KEYS = ["status", "urgency", "brand"] as const;

export default function ProblemCardsPage() {
  const t = useTranslations("pages.problemCards");
  const tFilters = useTranslations("pages.problemCards.filters");
  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<ProblemCard>({
    path: "/api/v1/problem-cards",
    pageSize: PAGE_SIZE,
    formatError: formatProblemCardError,
  });

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-secondary)]">
              {t("breadcrumb")}
            </span>
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              {t("title")}
            </h1>
          </div>

          <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">{t("totalLabelPrefix")}</span>
            <span className="text-[13px] font-bold text-[var(--text-primary)]">
              {loading && items.length === 0 ? "—" : items.length}
            </span>
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">
              {hasMore ? t("totalCardsMore") : t("totalCards")}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          {FILTER_KEYS.map((key) => (
            <button
              key={key}
              disabled
              title={t("comingSoonTitle")}
              className="flex h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60 cursor-not-allowed"
            >
              <span className="text-[13px] text-[var(--text-secondary)]">{tFilters(key)}</span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          ))}

          <button
            disabled
            title={t("comingSoonTitle")}
            className="flex h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60 cursor-not-allowed"
          >
            <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[13px] text-[var(--text-secondary)]">{tFilters("dateRange")}</span>
            <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>

          <div className="flex h-9 flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              placeholder={t("searchPlaceholder")}
              disabled
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)] cursor-not-allowed"
            />
          </div>
        </div>

        <main className="flex-1 overflow-auto bg-[var(--bg-page)] px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {t("loadFailed", { error })}
            </div>
          )}

          <ProblemCardsTable items={items} loading={loading} />

          {hasMore && items.length > 0 && (
            <div className="mt-4 flex justify-center">
              <button
                disabled={loading}
                onClick={loadMore}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? t("loadingMore") : t("loadMore")}
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
