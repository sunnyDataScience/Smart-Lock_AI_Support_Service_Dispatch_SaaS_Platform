"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Plus, Download } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import CaseCardGrid from "@/components/knowledge-base/CaseCardGrid";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, auth, tenantPath } from "@/lib/api";
import { kbDocumentToCaseEntry, type KBDocument } from "@/lib/kb-adapter";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];
type CaseSearchResponse = components["schemas"]["CaseSearchResponse"];
type KbExportRequest = components["schemas"]["KbExportRequest"];
type KbExportJob = components["schemas"]["KbExportJob"];
type KbExportScope = NonNullable<KbExportRequest["scope"]>;

function formatCasesError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

const PAGE_SIZE = 20;

const BRAND_OPTIONS = [
  "Chatlock",
  "Dormakaba",
  "Philips",
  "Kaadas",
  "Milre",
  "AiLock",
  "3E",
  "Waferlock",
];

type VerifiedFilter = "" | "true" | "false";

export default function CasesPage() {
  const pathname = usePathname();
  const tKb = useTranslations("kb");
  const tTabs = useTranslations("kb.tabs");
  const tC = useTranslations("kb.cases");

  const EXPORT_SCOPES: { value: KbExportScope; label: string; hint: string }[] = useMemo(
    () => [
      { value: "all", label: tC("scopeAll"), hint: tC("scopeAllHint") },
      { value: "cases_only", label: tC("scopeCases"), hint: tC("scopeCasesHint") },
      { value: "manuals_only", label: tC("scopeManuals"), hint: tC("scopeManualsHint") },
    ],
    [tC],
  );

  const tabs = useMemo(
    () => [
      { label: tTabs("cases"), href: "/knowledge-base/cases", dynamic: true },
      { label: tTabs("manuals"), href: "/knowledge-base/manuals", count: 23 },
      { label: tTabs("sopDrafts"), href: "/knowledge-base/sop-drafts", count: 7 },
    ],
    [tTabs],
  );

  const [brand, setBrand] = useState<string>("");
  const [verified, setVerified] = useState<VerifiedFilter>("");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<
    { case: CaseEntry; score: number }[] | null
  >(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exportPending, setExportPending] = useState(false);
  const [exportToast, setExportToast] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // P2-W3: 改用 v2 /kb/documents?doc_type=case（X-Tenant-ID 由 api.ts rawRequest 自動帶）
  // legacy /api/v1/knowledge-base/cases 仍保留（Deprecation header，P3 前不移除）
  const mainListQueryV2 = useMemo(() => {
    const q: Record<string, string | number | boolean | undefined> = {
      doc_type: "case",
    };
    if (brand) q.brand = brand;
    // verified filter 為 case-specific 欄位，v2 透過 meta.verified 傳回；
    // list 端點不支援 verified server-side filter，前端端篩選或待後續 server 端擴充
    return q;
  }, [brand]);

  const {
    items: rawItems,
    cursor,
    hasMore,
    totalCount,
    loading,
    error,
    loadMore,
  } = usePaginatedFetch<Record<string, unknown>>({
    path: "/kb/documents",
    pageSize: PAGE_SIZE,
    query: mainListQueryV2,
    queryKey: `brand=${brand}|verified=${verified}|v2`,
    formatError: formatCasesError,
  });

  // KBDocument → CaseEntry 欄位展開（meta 子物件攤平回 CaseEntry shape）
  const items = useMemo<CaseEntry[]>(() => {
    return rawItems
      .map((doc) => {
        const meta = (doc.meta ?? {}) as Record<string, unknown>;
        return {
          id: doc.id as string,
          title: doc.title as string,
          problem_description: (meta.problem_description ?? "") as string,
          solution: (meta.solution ?? "") as string,
          brand: (meta.brand ?? "") as string,
          model: (meta.model != null ? String(meta.model) : undefined),
          tags: (meta.tags != null ? (meta.tags as string[]) : undefined),
          verified: Boolean(meta.verified),
          embedding_status: (meta.embedding_status ?? "processing") as CaseEntry["embedding_status"],
          created_at: (meta.created_at ?? new Date().toISOString()) as string,
          updated_at: (meta.updated_at ?? new Date().toISOString()) as string,
        };
      })
      .filter((c) =>
        verified === ""
          ? true
          : verified === "true"
            ? c.verified
            : !c.verified,
      );
  }, [rawItems, verified]);

  useEffect(() => {
    const t = setTimeout(() => {
      setSearchQuery(searchInput.trim());
    }, 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    if (!searchQuery) {
      setSearchHits(null);
      setSearchError(null);
      setSearchLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setSearchLoading(true);
      setSearchError(null);
      try {
        const body: Record<string, unknown> = {
          query: searchQuery,
          limit: 20,
          similarity_threshold: 0.3,
        };
        if (brand) body.brand = brand;
        // CR-0005 step 3/3：v2 :search 走 kb_v2.py:searchKBDocuments
        // response.hits[].case 為 KBDocument meta-wrap；用 adapter 轉 CaseEntry
        body.doc_type = "case";
        const res = await api.post<{ hits: { case: KBDocument; score: number }[] }>(
          tenantPath("/kb/documents:search"),
          body,
        );
        if (!cancelled) {
          const adapted: CaseSearchResponse["hits"] = (res.hits ?? []).map((h) => ({
            case: kbDocumentToCaseEntry(h.case),
            score: h.score,
          }));
          setSearchHits(adapted);
        }
      } catch (e) {
        if (!cancelled) {
          setSearchError(
            e instanceof ApiError
              ? `${e.errorCode} (${e.status})：${e.message}`
              : e instanceof Error
                ? e.message
                : String(e),
          );
          setSearchHits([]);
        }
      } finally {
        if (!cancelled) setSearchLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchQuery, brand]);

  useEffect(() => {
    if (!exportToast) return;
    const t = setTimeout(() => setExportToast(null), 2400);
    return () => clearTimeout(t);
  }, [exportToast]);

  const handleExport = async (scope: KbExportScope) => {
    setExportPending(true);
    setExportError(null);
    setExportMenuOpen(false);
    try {
      const body: KbExportRequest = { scope };
      if (brand) body.brand = brand;
      const job = await api.post<KbExportJob>(
        "/api/v1/knowledge-base/export",
        body,
      );
      if (!job.download_url) {
        throw new Error(tC("exportNoUrl"));
      }
      const token = auth.getAccessToken();
      const tenantId = auth.getTenantId();
      const res = await fetch(job.download_url, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          "X-Tenant-ID": tenantId,
        },
      });
      if (!res.ok) {
        throw new Error(tC("exportDownloadFail", { status: res.status }));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kb-export-${job.job_id.slice(0, 8)}.jsonl`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      const scopeLabel = EXPORT_SCOPES.find((s) => s.value === scope)?.label ?? scope;
      setExportToast(
        tC("exportToast", { count: job.item_count ?? 0, scope: scopeLabel }),
      );
    } catch (e) {
      setExportError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setExportPending(false);
    }
  };

  const hasFilters = brand !== "" || verified !== "";
  const inSearchMode = searchQuery !== "";
  const displayItems = inSearchMode
    ? (searchHits ?? []).map((h) => h.case)
    : items;
  const displayLoading = inSearchMode ? searchLoading : loading;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {tKb("breadcrumbHome")} &gt; {tKb("breadcrumbKb")} &gt; {tC("breadcrumbCases")}
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            {tKb("pageTitle")}
          </h1>

          <div className="flex">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const count = tab.dynamic ? totalCount ?? items.length : tab.count;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`px-5 py-3 text-sm ${
                    isActive
                      ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {tab.label} ({count})
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 focus-within:border-[var(--primary)]">
            <Search className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={tC("searchPlaceholder")}
              className="h-10 flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => setSearchInput("")}
                className="text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                {tC("clear")}
              </button>
            )}
          </div>

          <select
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)]"
            aria-label={tC("brandFilterLabel")}
          >
            <option value="">{tC("allBrands")}</option>
            {BRAND_OPTIONS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>

          <select
            value={verified}
            onChange={(e) => setVerified(e.target.value as VerifiedFilter)}
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)]"
            aria-label={tC("verifiedFilterLabel")}
          >
            <option value="">{tC("allStatuses")}</option>
            <option value="true">{tC("verified")}</option>
            <option value="false">{tC("unverified")}</option>
          </select>

          {hasFilters && (
            <button
              onClick={() => {
                setBrand("");
                setVerified("");
              }}
              className="h-10 rounded-lg px-3 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            >
              {tC("clearFilter")}
            </button>
          )}

          <div className="relative">
            <button
              type="button"
              onClick={() => setExportMenuOpen((v) => !v)}
              disabled={exportPending}
              className="flex h-10 items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-4 text-sm font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title={brand ? tC("exportTitleBrand", { brand }) : tC("exportTitleAll")}
            >
              <Download className="h-4 w-4" />
              {exportPending ? tC("exporting") : tC("exportButton")}
            </button>
            {exportMenuOpen && (
              <div className="absolute right-0 top-full z-30 mt-1 w-48 overflow-hidden rounded-md border border-[var(--border)] bg-white shadow-lg">
                {EXPORT_SCOPES.map((s) => (
                  <button
                    key={s.value}
                    type="button"
                    onClick={() => handleExport(s.value)}
                    className="flex w-full flex-col items-start gap-[2px] px-3 py-2 text-left transition hover:bg-[var(--bg-page)]"
                  >
                    <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {s.label}
                    </span>
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      {s.hint}
                      {brand ? tC("exportLimitedToBrand", { brand }) : ""}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <Link
            href="/knowledge-base/cases/new"
            className="flex h-10 items-center gap-2 rounded-lg bg-[var(--primary)] px-5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
          >
            <Plus className="h-4 w-4" />
            {tC("addCase")}
          </Link>
        </div>

        {exportError && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {tC("exportError", { error: exportError })}
          </div>
        )}

        {exportToast && (
          <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
            {exportToast}
          </div>
        )}

        {(error || searchError) && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {searchError ?? error}
          </div>
        )}

        {inSearchMode && !searchLoading && !searchError && (
          <div className="mx-8 mt-4 rounded-lg border border-[var(--border)] bg-[#F8FAFC] px-4 py-2 text-[12px] text-[var(--text-secondary)]">
            {tC("searchHits", {
              query: searchQuery,
              count: searchHits?.length ?? 0,
            })}
            {brand && tC("searchHitsBrand", { brand })}
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <CaseCardGrid
            items={displayItems}
            loading={displayLoading}
            hasMore={inSearchMode ? false : hasMore}
            totalCount={inSearchMode ? displayItems.length : totalCount}
            onLoadMore={loadMore}
          />
        </div>
      </div>
    </div>
  );
}
