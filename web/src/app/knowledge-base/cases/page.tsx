"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Plus, Download } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import CaseCardGrid from "@/components/knowledge-base/CaseCardGrid";
import { ApiError, api, auth } from "@/lib/api";
import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];
type CaseEntryPage = components["schemas"]["CaseEntryPage"];
type CaseSearchResponse = components["schemas"]["CaseSearchResponse"];
type KbExportRequest = components["schemas"]["KbExportRequest"];
type KbExportJob = components["schemas"]["KbExportJob"];
type KbExportScope = NonNullable<KbExportRequest["scope"]>;

const EXPORT_SCOPES: { value: KbExportScope; label: string; hint: string }[] = [
  { value: "all", label: "全部", hint: "案例 + 手冊" },
  { value: "cases_only", label: "僅案例", hint: "case_entries" },
  { value: "manuals_only", label: "僅手冊", hint: "manuals" },
];

const tabs = [
  { label: "案例庫", href: "/knowledge-base/cases", dynamic: true },
  { label: "產品手冊", href: "/knowledge-base/manuals", count: 23 },
  { label: "SOP 草稿", href: "/knowledge-base/sop-drafts", count: 7 },
];

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
  const [items, setItems] = useState<CaseEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  const fetchPage = useCallback(
    async (
      afterCursor: string | null,
      append: boolean,
      filters: { brand: string; verified: VerifiedFilter },
    ) => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number | boolean> = { limit: PAGE_SIZE };
        if (afterCursor) query.cursor = afterCursor;
        if (filters.brand) query.brand = filters.brand;
        if (filters.verified !== "") query.verified = filters.verified === "true";
        const res = await api.get<CaseEntryPage>("/api/v1/knowledge-base/cases", { query });
        const newItems = res.items ?? [];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        setCursor(res.next_cursor ?? null);
        setHasMore(!!res.has_more);
        if (typeof res.total_count === "number") setTotalCount(res.total_count);
        else if (!append) setTotalCount(undefined);
      } catch (e) {
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    fetchPage(null, false, { brand, verified });
  }, [fetchPage, brand, verified]);

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
        const res = await api.post<CaseSearchResponse>(
          "/api/v1/knowledge-base/cases/search",
          body,
        );
        if (!cancelled) setSearchHits(res.hits ?? []);
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
        throw new Error("匯出任務未提供下載連結");
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
        throw new Error(`下載失敗（HTTP ${res.status}）`);
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
      setExportToast(`已匯出 ${job.item_count ?? 0} 筆（${scopeLabel}）`);
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
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; 案例庫
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            知識庫管理
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

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 focus-within:border-[var(--primary)]">
            <Search className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="輸入關鍵字搜尋案例（標題 / 問題 / 解決方案）"
              className="h-10 flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => setSearchInput("")}
                className="text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                清除
              </button>
            )}
          </div>

          <select
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)]"
            aria-label="品牌篩選"
          >
            <option value="">全部品牌</option>
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
            aria-label="驗證狀態篩選"
          >
            <option value="">全部狀態</option>
            <option value="true">已驗證</option>
            <option value="false">未驗證</option>
          </select>

          {hasFilters && (
            <button
              onClick={() => {
                setBrand("");
                setVerified("");
              }}
              className="h-10 rounded-lg px-3 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            >
              清除篩選
            </button>
          )}

          <div className="relative">
            <button
              type="button"
              onClick={() => setExportMenuOpen((v) => !v)}
              disabled={exportPending}
              className="flex h-10 items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-4 text-sm font-semibold text-[var(--text-primary)] transition hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title={brand ? `將以品牌「${brand}」過濾匯出` : "匯出全租戶知識庫"}
            >
              <Download className="h-4 w-4" />
              {exportPending ? "匯出中…" : "匯出索引"}
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
                      {brand ? ` · 限 ${brand}` : ""}
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
            新增案例
          </Link>
        </div>

        {exportError && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            匯出失敗：{exportError}
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
            {`搜尋「${searchQuery}」找到 ${searchHits?.length ?? 0} 筆相關案例`}
            {brand && `（限品牌：${brand}）`}
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <CaseCardGrid
            items={displayItems}
            loading={displayLoading}
            hasMore={inSearchMode ? false : hasMore}
            totalCount={inSearchMode ? displayItems.length : totalCount}
            onLoadMore={() => fetchPage(cursor, true, { brand, verified })}
          />
        </div>
      </div>
    </div>
  );
}
