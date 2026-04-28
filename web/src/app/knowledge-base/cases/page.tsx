"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import CaseCardGrid from "@/components/knowledge-base/CaseCardGrid";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type CaseEntry = components["schemas"]["CaseEntry"];
type CaseEntryPage = components["schemas"]["CaseEntryPage"];

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

  const hasFilters = brand !== "" || verified !== "";

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
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 opacity-60">
            <Search className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="搜尋案例（即將推出）"
              disabled
              className="h-10 flex-1 cursor-not-allowed bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
            />
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

          <Link
            href="/knowledge-base/cases/new"
            className="flex h-10 items-center gap-2 rounded-lg bg-[var(--primary)] px-5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
          >
            <Plus className="h-4 w-4" />
            新增案例
          </Link>
        </div>

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <CaseCardGrid
            items={items}
            loading={loading}
            hasMore={hasMore}
            totalCount={totalCount}
            onLoadMore={() => fetchPage(cursor, true, { brand, verified })}
          />
        </div>
      </div>
    </div>
  );
}
