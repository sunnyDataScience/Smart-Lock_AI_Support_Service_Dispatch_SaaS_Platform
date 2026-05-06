"use client";

import { useCallback, useEffect, useState } from "react";
import { Calendar, ChevronDown, Search } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ProblemCardsTable from "@/components/problem-cards/ProblemCardsTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardPage = components["schemas"]["ProblemCardPage"];

const PAGE_SIZE = 20;

const filters = ["狀態篩選", "緊急度", "品牌"];

export default function ProblemCardsPage() {
  const [items, setItems] = useState<ProblemCard[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(async (afterCursor: string | null, append: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: PAGE_SIZE };
      if (afterCursor) query.cursor = afterCursor;
      const res = await api.get<ProblemCardPage>("/api/v1/problem-cards", { query });
      const newItems = res.items ?? [];
      setItems((prev) => (append ? [...prev, ...newItems] : newItems));
      setCursor(res.next_cursor ?? null);
      setHasMore(!!res.has_more);
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
  }, []);

  useEffect(() => {
    fetchPage(null, false);
  }, [fetchPage]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 問題卡片
            </span>
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              問題卡片管理
            </h1>
          </div>

          <div className="flex items-center gap-[6px] rounded-md bg-[#F1F5F9] px-3 py-[6px]">
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">共</span>
            <span className="text-[13px] font-bold text-[var(--text-primary)]">
              {loading && items.length === 0 ? "—" : items.length}
            </span>
            <span className="text-[13px] font-medium text-[var(--text-secondary)]">
              {hasMore ? "+ 張卡片" : "張卡片"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
          {filters.map((label) => (
            <button
              key={label}
              disabled
              title="即將推出"
              className="flex h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60 cursor-not-allowed"
            >
              <span className="text-[13px] text-[var(--text-secondary)]">{label}</span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          ))}

          <button
            disabled
            title="即將推出"
            className="flex h-9 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60 cursor-not-allowed"
          >
            <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[13px] text-[var(--text-secondary)]">日期範圍</span>
            <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>

          <div className="flex h-9 flex-1 items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-4 w-4 text-[var(--text-disabled)]" />
            <input
              type="text"
              placeholder="搜尋功能即將推出"
              disabled
              className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-disabled)] cursor-not-allowed"
            />
          </div>
        </div>

        <main className="flex-1 overflow-auto bg-[var(--bg-page)] px-8 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入問題卡失敗：{error}
            </div>
          )}

          <ProblemCardsTable items={items} loading={loading} />

          {hasMore && items.length > 0 && (
            <div className="mt-4 flex justify-center">
              <button
                disabled={loading}
                onClick={() => fetchPage(cursor, true)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
