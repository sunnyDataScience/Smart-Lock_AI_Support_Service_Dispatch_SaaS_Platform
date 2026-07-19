"use client";

import { useMemo } from "react";
import Link from "next/link";
import { formatRelative } from "@/lib/format";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type Urgency = components["schemas"]["Urgency"];

interface Props {
  items: ProblemCard[];
  loading?: boolean;
}

// Tone（顏色）與 label（i18n 字串）分離 — 同 WorkOrdersTable 的設計約束
const STATUS_TONE: Record<ProblemCardStatus, { color: string; bg: string }> = {
  draft: { color: "#6366F1", bg: "#EEF2FF" },
  confirmed: { color: "#2563EB", bg: "#DBEAFE" },
  resolved: { color: "#10B981", bg: "#D1FAE5" },
};

const URGENCY_TONE: Record<Urgency, { color: string; bg: string }> = {
  low: { color: "#64748B", bg: "#F1F5F9" },
  medium: { color: "#D97706", bg: "#FEF3C7" },
  high: { color: "#EF4444", bg: "#FEE2E2" },
};

function shortId(id: string): string {
  return id.slice(0, 8);
}

export default function ProblemCardsTable({ items, loading }: Props) {
  const tCols = useTranslations("tables.problemCards.cols");
  const tTable = useTranslations("tables.problemCards");
  const tEmpty = useTranslations("tables");
  const tStatus = useTranslations("problemCardStatus");
  const tUrgency = useTranslations("urgency");

  const columns = useMemo(
    () => [
      { key: "id", label: tCols("id"), width: "w-[180px] shrink-0" },
      { key: "symptom", label: tCols("symptom"), width: "flex-1 min-w-0" },
      { key: "status", label: tCols("status"), width: "w-[90px] shrink-0" },
      { key: "urgency", label: tCols("urgency"), width: "w-[70px] shrink-0" },
      { key: "category", label: tCols("category"), width: "w-[80px] shrink-0" },
      { key: "brand", label: tCols("brand"), width: "w-[80px] shrink-0" },
      { key: "model", label: tCols("model"), width: "w-[100px] shrink-0" },
      { key: "createdAt", label: tCols("createdAt"), width: "w-[90px] shrink-0" },
    ],
    [tCols],
  );

  return (
    // UAT R3-12：390 窄幅外層改 overflow-x-auto（表頭不疊印、右側欄位可捲達），
    // 內層 min-w 撐出完整欄寬
    <div
      className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]"
      aria-label={tTable("ariaLabel")}
    >
      <div className="min-w-[880px]">
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
        {columns.map((col) => (
          <div key={col.key} className={`${col.width} px-0`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {items.length === 0 && !loading && (
        <div className="flex h-24 items-center justify-center">
          <span className="text-[13px] text-[var(--text-secondary)]">{tEmpty("empty")}</span>
        </div>
      )}

      {items.map((card, idx) => {
        const statusTone = STATUS_TONE[card.status];
        const urgencyTone = URGENCY_TONE[card.urgency];
        return (
          <Link
            key={card.id}
            href={`/problem-cards/${card.id}`}
            // UAT R3-12：zebra 偶數列 bg-white → semantic token（比照 WorkOrdersTable），
            // 深色主題不再白底近白字（1.07:1）
            className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] ${
              idx % 2 === 0 ? "bg-[var(--bg-surface)]" : "bg-[var(--bg-page)]"
            }`}
          >
            <div className="w-[180px] shrink-0">
              <span className="font-mono text-[12px] text-[var(--text-primary)]" title={card.id}>
                {shortId(card.id)}
              </span>
            </div>
            <div className="flex-1 min-w-0 truncate pr-4">
              {card.source === "ai_line" && (
                <span
                  className="mr-2 rounded px-[6px] py-[2px] text-[10px] font-semibold align-middle"
                  style={{ color: "#7C3AED", backgroundColor: "#F3E8FF" }}
                  title={
                    card.ai_missing_fields && card.ai_missing_fields.length > 0
                      ? tTable("aiDraftPendingTitle", {
                          fields: card.ai_missing_fields.join("、"),
                        })
                      : tTable("aiDraftReviewTitle")
                  }
                >
                  {tTable("aiDraftChip")}
                </span>
              )}
              <span className="text-[13px] text-[var(--text-primary)] align-middle">
                {card.symptom || "—"}
              </span>
              {card.source === "ai_line" &&
                card.ai_missing_fields &&
                card.ai_missing_fields.length > 0 && (
                  <span className="ml-2 text-[11px] text-[var(--text-disabled)] align-middle">
                    {tTable("aiMissingFields", {
                      fields: card.ai_missing_fields.join("、"),
                    })}
                  </span>
                )}
            </div>
            <div className="w-[90px] shrink-0">
              <span
                className="rounded-full px-[10px] py-1 text-[11px] font-medium"
                style={{ color: statusTone.color, backgroundColor: statusTone.bg }}
              >
                {tStatus(card.status)}
              </span>
            </div>
            <div className="w-[70px] shrink-0">
              <span
                className="rounded px-2 py-1 text-[11px] font-medium"
                style={{ color: urgencyTone.color, backgroundColor: urgencyTone.bg }}
              >
                {tUrgency(card.urgency)}
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
    </div>
  );
}
