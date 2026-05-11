"use client";

import { useMemo } from "react";
import { Search, ChevronDown, Wrench, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import TechniciansTable from "@/components/technicians/TechniciansTable";
import { ApiError } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];

function formatTechnicianError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const PAGE_SIZE = 20;

// Stable keys for filter labels — resolved per-render via i18n
const FILTER_DROPDOWN_KEYS = [
  "status",
  "brandSpecialty",
  "serviceArea",
  "rating",
] as const;

export default function TechniciansPage() {
  const t = useTranslations("pages.technicians");
  const tFilters = useTranslations("pages.technicians.filters");

  const filterDropdowns = useMemo(
    () =>
      FILTER_DROPDOWN_KEYS.map((key) => ({
        key,
        label: tFilters(key),
        hasChevron: true,
      })),
    [tFilters],
  );
  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<Technician>({
    path: "/api/v1/technicians",
    pageSize: PAGE_SIZE,
    formatError: formatTechnicianError,
  });

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Page Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex items-center gap-3">
            <Wrench className="h-6 w-6 text-[var(--primary)]" />
            <div className="flex flex-col gap-[2px]">
              <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
                {t("title")}
              </h1>
            </div>
            <span className="ml-1 flex items-center rounded-xl bg-[#DBEAFE] px-3 py-1 text-xs font-semibold text-[var(--primary)]">
              {loading && items.length === 0
                ? t("loadingBadge")
                : hasMore
                  ? t("techCountMore", { count: items.length })
                  : t("techCount", { count: items.length })}
            </span>
          </div>

          <button
            disabled
            title={t("comingSoonTitle")}
            className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-5 py-[10px] opacity-60 cursor-not-allowed"
          >
            <Plus className="h-4 w-4 text-white" />
            <span className="text-sm font-semibold text-white">{t("addTechnician")}</span>
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          {/* Search disabled */}
          <div className="flex h-[38px] w-[280px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              placeholder={t("searchPlaceholder")}
              disabled
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)] cursor-not-allowed"
            />
          </div>

          {/* Filter Dropdowns disabled */}
          {filterDropdowns.map((dd) => (
            <button
              key={dd.key}
              disabled
              title={t("comingSoonTitle")}
              className="flex h-[38px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60 cursor-not-allowed"
            >
              <span className="text-[13px] text-[var(--text-primary)]">
                {dd.label}
              </span>
              {dd.hasChevron && (
                <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              )}
            </button>
          ))}
        </div>

        {/* Table Area */}
        <main className="flex flex-1 flex-col gap-4 overflow-auto bg-[var(--bg-page)]">
          {error && (
            <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {t("loadFailed", { error })}
            </div>
          )}

          <TechniciansTable items={items} loading={loading} />

          {hasMore && items.length > 0 && (
            <div className="flex justify-center pb-6">
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
