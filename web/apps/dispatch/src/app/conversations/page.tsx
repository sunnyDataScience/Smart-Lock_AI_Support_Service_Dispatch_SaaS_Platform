"use client";

import { useMemo, useState } from "react";
import Sidebar from "@shared/components/layout/Sidebar";
import ConversationsTable from "@/components/conversations/ConversationsTable";
import { resolveTenantId } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { usePaginatedFetch } from "@shared/hooks/usePaginatedFetch";
import type { components } from "@shared/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationStatus = components["schemas"]["ConversationStatus"];
type StatusFilter = "" | ConversationStatus;

function formatConversationError(e: unknown): string {
  return friendlyError(e);
}

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
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");

  // CR-0003 P2-W2：遷移至 tenant-scoped v2 端點（FR-0018）
  const tenantId = resolveTenantId();

  const { items, hasMore, loading, error, loadMore } = usePaginatedFetch<Conversation>({
    path: `/tenants/${encodeURIComponent(tenantId)}/conversations`,
    pageSize: PAGE_SIZE,
    query: statusFilter ? { status: statusFilter } : undefined,
    queryKey: `status=${statusFilter}`,
    formatError: formatConversationError,
    // 有新對話/新訊息時自動刷新第一頁（15s 輪詢，bypass 快取；翻頁後自動暫停）
    pollIntervalMs: 15_000,
  });

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
