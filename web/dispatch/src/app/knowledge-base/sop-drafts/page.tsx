"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import SopDraftsList from "@/components/knowledge-base/SopDraftsList";
import { tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { usePaginatedFetch } from "@/hooks/usePaginatedFetch";
import { useKbCounts } from "@/hooks/useKbCounts";
import { kbDocumentToSopDraft, type KBDocumentSop } from "@/lib/kb-adapter";
import type { components } from "@/types/api.generated";

type SopDraft = components["schemas"]["SopDraft"];
type SopDraftStatus = components["schemas"]["SopDraftStatus"];

function formatSopDraftError(e: unknown): string {
  return friendlyError(e);
}

const PAGE_SIZE = 20;

const tabs = [
  { label: "案例庫", href: "/knowledge-base/cases", key: "cases" as const },
  { label: "產品手冊", href: "/knowledge-base/manuals", key: "manuals" as const },
  { label: "SOP 草稿", href: "/knowledge-base/sop-drafts", key: "sopDrafts" as const },
];

export default function SopDraftsPage() {
  const pathname = usePathname();
  const [statusFilter, setStatusFilter] = useState<SopDraftStatus | "">("");

  const kbCounts = useKbCounts();
  const { items, cursor, hasMore, loading, error, loadMore } = usePaginatedFetch<SopDraft>({
    // CR-0006 step 3/3：v2 GET sops/drafts + mapItem adapter（HD-01 meta-wrap → flat）
    path: tenantPath("/sops/drafts"),
    pageSize: PAGE_SIZE,
    query: statusFilter ? { status: statusFilter } : undefined,
    queryKey: `status=${statusFilter}`,
    formatError: formatSopDraftError,
    mapItem: (doc) => kbDocumentToSopDraft(doc as KBDocumentSop),
  });

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
              const count = kbCounts[tab.key] ?? "—";
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
            onLoadMore={loadMore}
          />
        </div>
      </div>
    </div>
  );
}
