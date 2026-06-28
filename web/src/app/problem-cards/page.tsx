"use client";

import { Calendar, ChevronDown, Search } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ProblemCardsTable from "@/components/problem-cards/ProblemCardsTable";
import { ApiError, resolveTenantId } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";
import { useMemo, useState } from "react";

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

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const tenantId = resolveTenantId();

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [urgencyFilter, setUrgencyFilter] = useState<string>("");
  const [brandFilter, setBrandFilter] = useState<string>("");
  const [periodFilter, setPeriodFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (statusFilter) p.set("status", statusFilter);
    if (urgencyFilter) p.set("urgency", urgencyFilter);
    if (brandFilter) p.set("brand", brandFilter);
    if (sourceFilter) p.set("source", sourceFilter);
    if (keyword.trim()) p.set("keyword", keyword.trim());
    if (periodFilter) {
      const days = parseInt(periodFilter, 10);
      if (!Number.isNaN(days)) {
        const since = new Date(Date.now() - days * 24 * 3600 * 1000);
        p.set("created_after", since.toISOString());
      }
    }
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  }, [statusFilter, urgencyFilter, brandFilter, periodFilter, sourceFilter, keyword]);

  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<ProblemCard>({
    path: `/tenants/${encodeURIComponent(tenantId)}/problem-cards${queryString}`,
    pageSize: PAGE_SIZE,
    formatError: formatProblemCardError,
  });

  const brandOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((c: any) => {
      if (c.brand) set.add(c.brand);
    });
    return Array.from(set).sort();
  }, [items]);

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
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("status")}</option>
            <option value="incomplete">未完成</option>
            <option value="complete">已完成</option>
            <option value="resolved">已處理</option>
          </select>

          <select
            value={urgencyFilter}
            onChange={(e) => setUrgencyFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("urgency")}</option>
            <option value="low">低</option>
            <option value="normal">一般</option>
            <option value="high">高</option>
            <option value="critical">緊急</option>
          </select>

          <select
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("brand")}</option>
            {brandOptions.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>

          <select
            value={periodFilter}
            onChange={(e) => setPeriodFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("dateRange")}</option>
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
            <option value="90">最近 90 天</option>
          </select>

          {/* CR-0022：來源篩選 — 「AI 草擬」即 LINE agent 轉真人待客服人審轉工單的佇列 */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="h-9 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
          >
            <option value="">{tFilters("source")}</option>
            <option value="ai_line">AI 草擬（待轉工單）</option>
            <option value="human">客服手建</option>
          </select>

          <div className="flex h-9 flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3">
            <Search className="h-4 w-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="flex-1 bg-transparent text-[13px] outline-none"
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
