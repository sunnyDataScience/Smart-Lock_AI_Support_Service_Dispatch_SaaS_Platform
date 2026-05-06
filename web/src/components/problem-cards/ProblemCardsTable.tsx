"use client";

import Link from "next/link";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type Urgency = components["schemas"]["Urgency"];

interface Props {
  items: ProblemCard[];
  loading?: boolean;
}

const statusStyles: Record<ProblemCardStatus, { label: string; color: string; bg: string }> = {
  draft: { label: "待確認", color: "#6366F1", bg: "#EEF2FF" },
  confirmed: { label: "已確認", color: "#2563EB", bg: "#DBEAFE" },
  resolved: { label: "已解決", color: "#10B981", bg: "#D1FAE5" },
};

const urgencyStyles: Record<Urgency, { label: string; color: string; bg: string }> = {
  low: { label: "低", color: "#64748B", bg: "#F1F5F9" },
  medium: { label: "中", color: "#D97706", bg: "#FEF3C7" },
  high: { label: "高", color: "#EF4444", bg: "#FEE2E2" },
};

const columns = [
  { label: "卡片 ID", width: "w-[180px] shrink-0" },
  { label: "症狀摘要", width: "flex-1 min-w-0" },
  { label: "狀態", width: "w-[90px] shrink-0" },
  { label: "緊急度", width: "w-[70px] shrink-0" },
  { label: "類別", width: "w-[80px] shrink-0" },
  { label: "品牌", width: "w-[80px] shrink-0" },
  { label: "型號", width: "w-[100px] shrink-0" },
  { label: "建立時間", width: "w-[90px] shrink-0" },
];

function shortId(id: string): string {
  return id.slice(0, 8);
}

export default function ProblemCardsTable({ items, loading }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
        {columns.map((col) => (
          <div key={col.label} className={`${col.width} px-0`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {items.length === 0 && !loading && (
        <div className="flex h-24 items-center justify-center">
          <span className="text-[13px] text-[var(--text-secondary)]">目前無資料</span>
        </div>
      )}

      {items.map((card, idx) => {
        const status = statusStyles[card.status];
        const urgency = urgencyStyles[card.urgency];
        return (
          <Link
            key={card.id}
            href={`/problem-cards/${card.id}`}
            className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] ${
              idx % 2 === 0 ? "bg-white" : "bg-[var(--bg-page)]"
            }`}
          >
            <div className="w-[180px] shrink-0">
              <span className="font-mono text-[12px] text-[var(--text-primary)]" title={card.id}>
                {shortId(card.id)}
              </span>
            </div>
            <div className="flex-1 min-w-0 truncate pr-4">
              <span className="text-[13px] text-[var(--text-primary)]">
                {card.symptom || "—"}
              </span>
            </div>
            <div className="w-[90px] shrink-0">
              <span
                className="rounded-full px-[10px] py-1 text-[11px] font-medium"
                style={{ color: status.color, backgroundColor: status.bg }}
              >
                {status.label}
              </span>
            </div>
            <div className="w-[70px] shrink-0">
              <span
                className="rounded px-2 py-1 text-[11px] font-medium"
                style={{ color: urgency.color, backgroundColor: urgency.bg }}
              >
                {urgency.label}
              </span>
            </div>
            <div className="w-[80px] shrink-0">
              <span className="text-[13px] text-[var(--text-primary)]">{card.category}</span>
            </div>
            <div className="w-[80px] shrink-0">
              <span className="text-[13px] text-[var(--text-primary)]">
                {card.brand || "—"}
              </span>
            </div>
            <div className="w-[100px] shrink-0">
              <span className="text-[13px] text-[var(--text-primary)]">
                {card.model || "—"}
              </span>
            </div>
            <div className="w-[90px] shrink-0">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {formatRelative(card.created_at)}
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
