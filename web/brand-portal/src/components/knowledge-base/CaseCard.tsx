"use client";

import Link from "next/link";
import type { components } from "@/types/api.generated";
import { formatRelative } from "@/lib/format";

type CaseEntry = components["schemas"]["CaseEntry"];
type EmbeddingStatus = CaseEntry["embedding_status"];

const EMBEDDING_LABEL: Record<EmbeddingStatus, { text: string; bg: string; color: string }> = {
  processing: { text: "索引中", bg: "#FEF3C7", color: "#92400E" },
  ready: { text: "已索引", bg: "#D1FAE5", color: "#065F46" },
  failed: { text: "索引失敗", bg: "#FEE2E2", color: "#991B1B" },
};

export default function CaseCard({ entry }: { entry: CaseEntry }) {
  const status = EMBEDDING_LABEL[entry.embedding_status];

  return (
    <Link
      href={`/knowledge-base/cases/${entry.id}`}
      className="flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5 shadow-sm transition hover:border-[var(--primary)] hover:shadow-md"
    >
      <h3 className="line-clamp-2 text-[15px] font-bold leading-snug text-[var(--text-primary)]">
        {entry.title}
      </h3>

      <div className="flex flex-wrap gap-2">
        <span className="rounded bg-[#EFF6FF] px-[10px] py-1 text-xs font-medium text-[var(--primary)]">
          {entry.brand}
        </span>
        {entry.model && (
          <span className="rounded bg-[#EFF6FF] px-[10px] py-1 text-xs font-medium text-[var(--primary)]">
            {entry.model}
          </span>
        )}
        {entry.verified ? (
          <span className="rounded bg-[#D1FAE5] px-[10px] py-1 text-xs font-medium text-[#065F46]">
            ✓ 已驗證
          </span>
        ) : (
          <span className="rounded bg-[#F1F5F9] px-[10px] py-1 text-xs font-medium text-[var(--text-secondary)]">
            未驗證
          </span>
        )}
      </div>

      <p className="line-clamp-2 text-[13px] text-[var(--text-secondary)]">
        {entry.problem_description}
      </p>

      <div className="flex items-center justify-between gap-2">
        <span
          className="rounded px-[10px] py-1 text-[11px] font-medium"
          style={{ backgroundColor: status.bg, color: status.color }}
        >
          {status.text}
        </span>
        <span className="text-xs text-[var(--text-secondary)]">
          更新於 {formatRelative(entry.updated_at)}
        </span>
      </div>
    </Link>
  );
}
