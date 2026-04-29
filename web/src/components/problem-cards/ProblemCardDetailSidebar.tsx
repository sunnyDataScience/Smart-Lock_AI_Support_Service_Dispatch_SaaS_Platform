"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
} from "@/components/work-orders/WorkOrdersTable";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

interface Props {
  card?: ProblemCard | null;
  loading?: boolean;
}

const PC_STATUS_STYLE: Record<
  ProblemCardStatus,
  { label: string; color: string; bg: string }
> = {
  draft: { label: "草稿", color: "#6366F1", bg: "#EEF2FF" },
  confirmed: { label: "已確認", color: "#3B82F6", bg: "#DBEAFE" },
  resolved: { label: "已解決", color: "#10B981", bg: "#D1FAE5" },
};

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  } catch {
    return iso;
  }
}

function technicianTag(id: string | null | undefined): string | null {
  if (!id) return null;
  return `技師 ${id.slice(0, 4)}`;
}

export default function ProblemCardDetailSidebar({ card, loading }: Props) {
  const [linked, setLinked] = useState<WorkOrder | null>(null);
  const [linkedLoading, setLinkedLoading] = useState(false);
  const [linkedError, setLinkedError] = useState<string | null>(null);

  useEffect(() => {
    if (!card) return;
    let cancelled = false;
    setLinkedLoading(true);
    setLinkedError(null);
    setLinked(null);
    (async () => {
      try {
        const res = await api.get<WorkOrderPage>("/api/v1/work-orders", {
          query: { limit: 100 },
        });
        if (cancelled) return;
        const items: WorkOrder[] = res.items ?? [];
        const match = items.find((wo) => wo.problem_card_id === card.id);
        setLinked(match ?? null);
      } catch (e) {
        if (cancelled) return;
        setLinkedError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (!cancelled) setLinkedLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [card]);

  const status = card ? PC_STATUS_STYLE[card.status] : null;

  return (
    <div className="flex w-[380px] flex-shrink-0 flex-col gap-4">
      {/* Status */}
      <div className="flex w-full flex-col gap-3 rounded-lg border border-[var(--border)] bg-white p-5">
        <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
          狀態
        </span>
        {loading && !card ? (
          <span className="text-[13px] text-[var(--text-disabled)]">
            載入中…
          </span>
        ) : status ? (
          <span
            className="self-start rounded-full px-3 py-1 text-[12px] font-semibold"
            style={{ color: status.color, backgroundColor: status.bg }}
          >
            {status.label}
          </span>
        ) : (
          <span className="text-[13px] text-[var(--text-disabled)]">—</span>
        )}
        {card?.confidence_score != null && (
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              AI 信心
            </span>
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              {(card.confidence_score * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {/* Timestamps */}
      <div className="flex w-full flex-col gap-3 rounded-lg border border-[var(--border)] bg-white p-5">
        <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
          時間紀錄
        </span>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            建立時間
          </span>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">
            {card ? formatDateTime(card.created_at) : "—"}
          </span>
        </div>
        <div className="flex items-start justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            最後更新
          </span>
          <div className="flex flex-col items-end gap-[2px]">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              {card ? formatDateTime(card.updated_at) : "—"}
            </span>
            <span className="text-[11px] text-[var(--text-disabled)]">
              {card ? formatRelative(card.updated_at) : ""}
            </span>
          </div>
        </div>
      </div>

      {/* Linked Work Order */}
      <div className="flex w-full overflow-hidden rounded-lg border border-[var(--border)] bg-white">
        <div className="w-[3px] flex-shrink-0 bg-[var(--primary)]" />
        <div className="flex w-full flex-col gap-3 p-5">
          <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
            關聯工單
          </span>
          {linkedError && (
            <span className="text-[12px] text-red-600">
              載入失敗：{linkedError}
            </span>
          )}
          {linkedLoading && !linked && (
            <span className="text-[13px] text-[var(--text-disabled)]">
              查詢中…
            </span>
          )}
          {!linkedLoading && !linked && !linkedError && card && (
            <span className="text-[13px] text-[var(--text-disabled)]">
              尚無關聯工單
            </span>
          )}
          {linked &&
            (() => {
              const group = STATUS_GROUP_MAP[linked.status];
              const woStyle = STATUS_GROUP_STYLE[group];
              const tech = technicianTag(linked.technician_id);
              return (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      工單編號
                    </span>
                    <Link
                      href={`/work-orders/${linked.id}`}
                      className="font-mono text-[13px] font-semibold text-[var(--primary)] hover:underline"
                      title={linked.id}
                    >
                      {linked.id.slice(0, 8)}
                    </Link>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      工單狀態
                    </span>
                    <span
                      className="rounded-full px-[10px] py-[3px] text-[11px] font-semibold"
                      style={{ color: woStyle.color, backgroundColor: woStyle.bg }}
                    >
                      {woStyle.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      指派技師
                    </span>
                    <span className="text-[13px] font-medium text-[var(--text-primary)]">
                      {tech ?? (
                        <span className="text-[var(--text-disabled)]">未指派</span>
                      )}
                    </span>
                  </div>
                </>
              );
            })()}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex w-full flex-col gap-2">
        <button
          type="button"
          disabled
          title="即將推出"
          className="w-full cursor-not-allowed rounded-lg bg-[#94A3B8]/60 py-[10px] text-center text-[14px] font-semibold text-white opacity-70"
        >
          標記已解決
        </button>
        <button
          type="button"
          disabled
          title="即將推出"
          className="w-full cursor-not-allowed rounded-lg bg-[#94A3B8]/60 py-[10px] text-center text-[14px] font-semibold text-white opacity-70"
        >
          升級至 L3 派工
        </button>
        <button
          type="button"
          disabled
          title="即將推出"
          className="w-full cursor-not-allowed rounded-lg border-[1.5px] border-[var(--primary)] bg-transparent py-[10px] text-center text-[14px] font-semibold text-[var(--primary)] opacity-60"
        >
          關聯知識案例
        </button>
      </div>
    </div>
  );
}
