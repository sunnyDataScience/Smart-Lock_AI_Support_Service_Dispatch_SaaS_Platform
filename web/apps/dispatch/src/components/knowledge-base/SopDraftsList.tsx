"use client";

import Link from "next/link";
import type { components } from "@shared/types/api.generated";
import { formatRelative } from "@shared/lib/format";

type SopDraft = components["schemas"]["SopDraft"];
type SopDraftStatus = components["schemas"]["SopDraftStatus"];

interface Props {
  items: SopDraft[];
  loading?: boolean;
  status: SopDraftStatus | "";
  onStatusChange: (s: SopDraftStatus | "") => void;
  hasMore: boolean;
  onLoadMore: () => void;
}

const statusConfig: Record<
  SopDraftStatus,
  { label: string; bg: string; text: string }
> = {
  draft: {
    label: "草稿",
    bg: "#F1F5F9",
    text: "var(--text-disabled)",
  },
  under_review: {
    label: "待審核",
    bg: "#FFFBEB",
    text: "var(--status-warning)",
  },
  approved: {
    label: "已核准",
    bg: "#ECFDF5",
    text: "var(--status-success)",
  },
  rejected: {
    label: "已拒絕",
    bg: "#FEF2F2",
    text: "var(--status-danger)",
  },
};

const STATUS_OPTIONS: { value: SopDraftStatus | ""; label: string }[] = [
  { value: "", label: "全部狀態" },
  { value: "under_review", label: "待審核" },
  { value: "approved", label: "已核准" },
  { value: "rejected", label: "已拒絕" },
];

function StatusBadge({ status }: { status: SopDraftStatus }) {
  const config = statusConfig[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-medium"
      style={{ backgroundColor: config.bg, color: config.text }}
    >
      {config.label}
    </span>
  );
}

export default function SopDraftsList({
  items,
  loading,
  status,
  onStatusChange,
  hasMore,
  onLoadMore,
}: Props) {
  return (
    <div className="flex flex-1 flex-col gap-4 px-8 py-6">
      {/* Filter Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <select
            value={status}
            onChange={(e) =>
              onStatusChange(e.target.value as SopDraftStatus | "")
            }
            className="h-10 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-[13px] text-[var(--text-primary)]"
            aria-label="狀態篩選"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                狀態：{o.label}
              </option>
            ))}
          </select>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {loading
            ? "載入中…"
            : `顯示 ${items.length} 筆${hasMore ? "（尚有更多）" : ""}`}
        </span>
      </div>

      {/* Empty / loading */}
      {!loading && items.length === 0 && (
        <div className="flex h-32 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-sm text-[var(--text-secondary)]">
          目前沒有符合條件的 SOP 草稿
        </div>
      )}

      {/* Queue List */}
      {items.length > 0 && (
        <div className="flex-1 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
          {items.map((item, idx) => (
            <Link
              key={item.id}
              href={`/knowledge-base/sop-drafts/${item.id}`}
              className={`flex items-start justify-between px-5 py-4 hover:bg-[var(--bg-page)] ${
                idx < items.length - 1
                  ? "border-b border-[var(--border)]"
                  : ""
              }`}
            >
              <div className="flex flex-col gap-[6px]">
                <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                  {item.title}
                </span>
                {item.problem_card_id ? (
                  <span className="text-[13px] text-[var(--primary)]">
                    來源問題卡：{item.problem_card_id.slice(0, 8)}
                  </span>
                ) : (
                  <span className="text-[13px] text-[var(--text-disabled)]">
                    來源：—
                  </span>
                )}
                <span className="text-xs text-[var(--text-secondary)]">
                  建立於 {formatRelative(item.created_at)} · {item.steps.length} 個步驟
                </span>
              </div>
              <div className="flex flex-col items-end gap-[6px]">
                <StatusBadge status={item.status} />
                {item.reviewed_at && (
                  <span className="text-xs text-[var(--text-secondary)]">
                    審核於 {formatRelative(item.reviewed_at)}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Load more */}
      {hasMore && !loading && (
        <div className="flex justify-center">
          <button
            onClick={onLoadMore}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
          >
            載入更多
          </button>
        </div>
      )}
    </div>
  );
}
