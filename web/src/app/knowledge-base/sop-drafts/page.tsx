"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import SopDraftsList from "@/components/knowledge-base/SopDraftsList";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type SopDraft = components["schemas"]["SopDraft"];
type SopDraftPage = components["schemas"]["SopDraftPage"];
type SopDraftStatus = components["schemas"]["SopDraftStatus"];

const PAGE_SIZE = 20;

const tabs = [
  { label: "案例庫", href: "/knowledge-base/cases", count: 128 },
  { label: "產品手冊", href: "/knowledge-base/manuals", count: 6 },
  { label: "SOP 草稿", href: "/knowledge-base/sop-drafts", dynamic: true },
];

export default function SopDraftsPage() {
  const pathname = usePathname();
  const [items, setItems] = useState<SopDraft[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<SopDraftStatus | "">("");

  const fetchPage = useCallback(
    async (
      afterCursor: string | null,
      append: boolean,
      status: SopDraftStatus | "",
    ) => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number> = { limit: PAGE_SIZE };
        if (afterCursor) query.cursor = afterCursor;
        if (status) query.status = status;
        const res = await api.get<SopDraftPage>("/api/v1/sop-drafts", { query });
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
    },
    [],
  );

  useEffect(() => {
    fetchPage(null, false, statusFilter);
  }, [fetchPage, statusFilter]);

  const showCount = hasMore ? `${items.length}+` : items.length;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header */}
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; SOP 草稿
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            知識庫管理
          </h1>

          {/* Tab Bar */}
          <div className="flex">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const count = tab.dynamic ? showCount : tab.count;
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

        {error && (
          <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* SOP Drafts List */}
        <div className="flex-1 overflow-auto">
          <SopDraftsList
            items={items}
            loading={loading}
            status={statusFilter}
            onStatusChange={setStatusFilter}
            hasMore={hasMore}
            onLoadMore={() => fetchPage(cursor, true, statusFilter)}
          />
        </div>
      </div>
    </div>
  );
}
