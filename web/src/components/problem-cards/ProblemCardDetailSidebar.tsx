"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ApiError, api, tenantPath } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

interface Props {
  card?: ProblemCard | null;
  loading?: boolean;
}

// Tone（顏色）固定；label 由 i18n 提供
const PC_STATUS_TONE: Record<
  ProblemCardStatus,
  { color: string; bg: string }
> = {
  draft: { color: "#6366F1", bg: "#EEF2FF" },
  confirmed: { color: "#3B82F6", bg: "#DBEAFE" },
  resolved: { color: "#10B981", bg: "#D1FAE5" },
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

export default function ProblemCardDetailSidebar({ card, loading }: Props) {
  const t = useTranslations("components.problemCards.detailSidebar");
  const tGroup = useTranslations("status.workOrderGroup");

  const groupLabels: Record<StatusGroup, string> = useMemo(
    () => ({
      pending: tGroup("pending"),
      dispatched: tGroup("dispatched"),
      in_progress: tGroup("in_progress"),
      done: tGroup("done"),
      cancelled: tGroup("cancelled"),
    }),
    [tGroup],
  );

  const statusLabels: Record<ProblemCardStatus, string> = useMemo(
    () => ({
      draft: t("status.draft"),
      confirmed: t("status.confirmed"),
      resolved: t("status.resolved"),
    }),
    [t],
  );

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
        const res = await api.get<WorkOrderPage>(tenantPath("/work-orders"), {
          query: { problem_card_id: card.id, limit: 1 },
        });
        if (cancelled) return;
        const items = (res.items ?? []) as WorkOrder[];
        setLinked(items[0] ?? null);
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

  const tone = card ? PC_STATUS_TONE[card.status] : null;
  const comingSoon = t("comingSoon");

  return (
    <div className="flex w-[380px] flex-shrink-0 flex-col gap-4">
      {/* Status */}
      <div className="flex w-full flex-col gap-3 rounded-lg border border-[var(--border)] bg-white p-5">
        <span className="text-[14px] font-semibold text-[var(--text-secondary)]">
          {t("statusTitle")}
        </span>
        {loading && !card ? (
          <span className="text-[13px] text-[var(--text-disabled)]">
            {t("loading")}
          </span>
        ) : tone && card ? (
          <span
            className="self-start rounded-full px-3 py-1 text-[12px] font-semibold"
            style={{ color: tone.color, backgroundColor: tone.bg }}
          >
            {statusLabels[card.status]}
          </span>
        ) : (
          <span className="text-[13px] text-[var(--text-disabled)]">—</span>
        )}
        {card?.confidence_score != null && (
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              {t("aiConfidence")}
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
          {t("timeTitle")}
        </span>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {t("createdAt")}
          </span>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">
            {card ? formatDateTime(card.created_at) : "—"}
          </span>
        </div>
        <div className="flex items-start justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">
            {t("updatedAt")}
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
            {t("linkedTitle")}
          </span>
          {linkedError && (
            <span className="text-[12px] text-red-600">
              {t("loadFailed", { error: linkedError })}
            </span>
          )}
          {linkedLoading && !linked && (
            <span className="text-[13px] text-[var(--text-disabled)]">
              {t("querying")}
            </span>
          )}
          {!linkedLoading && !linked && !linkedError && card && (
            <span className="text-[13px] text-[var(--text-disabled)]">
              {t("noLinked")}
            </span>
          )}
          {linked &&
            (() => {
              const group = STATUS_GROUP_MAP[linked.status];
              const woTone = STATUS_GROUP_TONE[group];
              const tech = linked.technician_id
                ? t("techTag", { id: linked.technician_id.slice(0, 4) })
                : null;
              return (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      {t("orderId")}
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
                      {t("orderStatus")}
                    </span>
                    <span
                      className="rounded-full px-[10px] py-[3px] text-[11px] font-semibold"
                      style={{ color: woTone.color, backgroundColor: woTone.bg }}
                    >
                      {groupLabels[group]}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      {t("technician")}
                    </span>
                    <span className="text-[13px] font-medium text-[var(--text-primary)]">
                      {tech ?? (
                        <span className="text-[var(--text-disabled)]">
                          {t("unassigned")}
                        </span>
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
          title={comingSoon}
          className="w-full cursor-not-allowed rounded-lg bg-[#94A3B8]/60 py-[10px] text-center text-[14px] font-semibold text-white opacity-70"
        >
          {t("markResolved")}
        </button>
        <button
          type="button"
          disabled
          title={comingSoon}
          className="w-full cursor-not-allowed rounded-lg bg-[#94A3B8]/60 py-[10px] text-center text-[14px] font-semibold text-white opacity-70"
        >
          {t("escalate")}
        </button>
        <button
          type="button"
          disabled
          title={comingSoon}
          className="w-full cursor-not-allowed rounded-lg border-[1.5px] border-[var(--primary)] bg-transparent py-[10px] text-center text-[14px] font-semibold text-[var(--primary)] opacity-60"
        >
          {t("linkCase")}
        </button>
      </div>
    </div>
  );
}
