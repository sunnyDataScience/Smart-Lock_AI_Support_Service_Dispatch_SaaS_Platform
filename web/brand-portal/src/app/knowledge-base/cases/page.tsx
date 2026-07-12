"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Plus, Download } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import CaseCardGrid from "@/components/knowledge-base/CaseCardGrid";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, auth } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { kbDocumentToCaseEntry, type KBDocument } from "@/lib/kb-adapter";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import { useKbCounts } from "@/hooks/useKbCounts";
import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];
type CaseSearchResponse = components["schemas"]["CaseSearchResponse"];

function formatCasesError(e: unknown): string {
  return friendlyError(e);
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

  const kbCounts = useKbCounts();
  const tabs = useMemo(
    () => [
      { label: tTabs("cases"), href: "/knowledge-base/cases", count: kbCounts.cases },
      { label: tTabs("manuals"), href: "/knowledge-base/manuals", count: kbCounts.manuals },
      { label: tTabs("sopDrafts"), href: "/knowledge-base/sop-drafts", count: kbCounts.sopDrafts },
      { label: tTabs("skills"), href: "/knowledge-base/skills", count: kbCounts.skills },
    ],
    [tTabs, kbCounts],
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
        // /kb/documents 為平台級 flat 端點（per api.ts:tenantPath docstring），
        // tenant 隔離由 X-Tenant-ID header + 服務端 require_tenant 把關
        // response.hits[].case 為 KBDocument meta-wrap；用 adapter 轉 CaseEntry
        body.doc_type = "case";
        const res = await api.post<{ hits: { case: KBDocument; score: number }[] }>(
          "/kb/documents:search",
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
            friendlyError(e),
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

  // CR-0005 step 3/3：v1 async-job → v2 :export 同步 CSV stream（HD-06=a CSV-first、case-only MVP）
  const handleExport = async () => {
    setExportPending(true);
    setExportError(null);
    try {
      const qs = new URLSearchParams({ doc_type: "case", format: "csv" });
      if (brand) qs.set("brand", brand);
      const token = auth.getAccessToken();
      const tenantId = auth.getTenantId();
      // /kb/documents 為平台級 flat 端點（per api.ts:tenantPath docstring），
      // 不套 tenantPath；tenant 隔離由 X-Tenant-ID header + require_tenant 服務端處理
      // 用 || 而非 ??：NEXT_PUBLIC_API_BASE_URL 在部分 build 被烤成空字串，
      // ?? 不會對空字串退回 → 變相對 URL 打到 web origin 而非 API（404）。對齊 api.ts:BASE_URL。
      const apiBase =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";
      const res = await fetch(
        `${apiBase}/kb/documents:export?${qs.toString()}`,
        {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            "X-Tenant-ID": tenantId,
          },
        },
      );
      if (!res.ok) {
        throw new Error(tC("exportDownloadFail", { status: res.status }));
      }
      const blob = await res.blob();
      // 從下載的 CSV 算真實匯出筆數（資料列＝總行數－表頭；後端已把自由文字內換行替成空白）
      const csvText = await blob.text();
      const exportedCount = csvText.trim()
        ? csvText.trim().split(/\r?\n/).length - 1
        : 0;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ts = new Date().toISOString().slice(0, 10);
      a.download = `kb-cases-${ts}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setExportToast(
        tC("exportToast", { count: exportedCount, scope: tC("scopeCases") }),
      );
    } catch (e) {
      setExportError(
        friendlyError(e),
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
              const count = tab.count ?? "—";
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

          {/* CR-0005 HD-06=a：v2 :export MVP scope = case-only CSV，故省略 scope dropdown；
              manual export 待 manual_service search 補完後另開 button */}
          <button
            type="button"
            onClick={() => handleExport()}
            disabled={exportPending}
            className="flex h-10 items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-4 text-sm font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
            title={brand ? tC("exportTitleBrand", { brand }) : tC("exportTitleAll")}
          >
            <Download className="h-4 w-4" />
            {exportPending ? tC("exporting") : tC("exportButton")}
          </button>

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
