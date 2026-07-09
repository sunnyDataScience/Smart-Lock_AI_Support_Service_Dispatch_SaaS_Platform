"use client";

import type { components } from "@/types/api.generated";
import CaseCard from "./CaseCard";

type CaseEntry = components["schemas"]["CaseEntry"];

interface Props {
  items: CaseEntry[];
  loading: boolean;
  hasMore: boolean;
  totalCount?: number;
  onLoadMore: () => void;
}

export default function CaseCardGrid({
  items,
  loading,
  hasMore,
  totalCount,
  onLoadMore,
}: Props) {
  return (
    <div className="flex flex-1 flex-col gap-5 px-8 py-6">
      {items.length === 0 && !loading ? (
        <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-[var(--border)] text-sm text-[var(--text-secondary)]">
          尚無案例。點右上「新增案例」開始建立。
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-5">
          {items.map((entry) => (
            <CaseCard key={entry.id} entry={entry} />
          ))}
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="text-[13px] text-[var(--text-secondary)]">
          {totalCount !== undefined
            ? `顯示 ${items.length} / ${totalCount} 筆`
            : `已載入 ${items.length} 筆`}
        </span>

        {hasMore && (
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loading}
            className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 text-sm font-medium text-[var(--text-primary)] transition hover:border-[var(--primary)] disabled:opacity-50"
          >
            {loading ? "載入中…" : "載入更多"}
          </button>
        )}
      </div>
    </div>
  );
}
