"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import ConversationsTable from "@/components/conversations/ConversationsTable";
import { ApiError, api } from "@/lib/api";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationPage = components["schemas"]["ConversationPage"];
type ConversationStatus = components["schemas"]["ConversationStatus"];
type StatusFilter = "" | ConversationStatus;

// Stable tab keys; labels resolved per-render via i18n
const TAB_DEFS: { value: StatusFilter; key: string }[] = [
  { value: "", key: "all" },
  { value: "active", key: "active" },
  { value: "waiting_human", key: "waiting_human" },
  { value: "closed", key: "closed" },
];

const PAGE_SIZE = 20;

export default function ConversationsPage() {
  const t = useTranslations("pages.conversations");
  const tTabs = useTranslations("pages.conversations.tabs");
  const TABS = useMemo(
    () => TAB_DEFS.map((d) => ({ value: d.value, label: tTabs(d.key) })),
    [tTabs],
  );
  const [items, setItems] = useState<Conversation[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");

  const fetchPage = useCallback(
    async (afterCursor: string | null, append: boolean, filter: StatusFilter) => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number> = { limit: PAGE_SIZE };
        if (afterCursor) query.cursor = afterCursor;
        if (filter) query.status = filter;
        const res = await api.get<ConversationPage>("/api/v1/conversations", { query });
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

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] py-3 pl-14 pr-4 md:px-4">
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-semibold text-[#18181B]">
              {t("title")}
            </h1>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex">
              {TABS.map((tab) => (
                <button
                  key={tab.value || "all"}
                  onClick={() => setStatusFilter(tab.value)}
                  className={`flex items-center gap-[6px] px-3 py-[10px] text-[14px] ${
                    statusFilter === tab.value
                      ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                      : "font-medium text-[#71717A]"
                  }`}
                >
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            <span className="ml-auto text-[13px] text-[var(--text-secondary)]">
              {loading
                ? t("loading")
                : hasMore
                  ? t("totalCountMore", { count: items.length })
                  : t("totalCount", { count: items.length })}
            </span>
          </div>
        </div>

        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-auto px-8 py-6"
        >
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <ConversationsTable items={items} loading={loading} />

          {hasMore && (
            <div className="mt-4 flex justify-center">
              <button
                disabled={loading}
                onClick={() => fetchPage(cursor, true, statusFilter)}
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
