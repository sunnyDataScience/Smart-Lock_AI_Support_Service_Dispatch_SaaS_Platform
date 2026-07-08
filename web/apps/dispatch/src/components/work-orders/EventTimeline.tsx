"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckSquare,
  Clock,
  PackageSearch,
  PenTool,
  RefreshCw,
  Wrench,
} from "lucide-react";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

type EventType =
  | "scope_change"
  | "material_request"
  | "delay"
  | "door_check"
  | "signature_submitted"
  | "reschedule_proposed"
  | "other";

interface WorkOrderEvent {
  id: string;
  event_type: EventType;
  payload: Record<string, unknown>;
  actor_user_id?: string | null;
  created_at: string;
}

// Tone（icon + 顏色）— 模組級不變；label 由 hook 提供
const TYPE_TONE: Record<
  EventType,
  {
    Icon: React.ComponentType<{
      className?: string;
      style?: React.CSSProperties;
    }>;
    color: string;
    bg: string;
  }
> = {
  scope_change: {
    Icon: Wrench,
    color: "#9A3412",
    bg: "#FFEDD5",
  },
  material_request: {
    Icon: PackageSearch,
    color: "#92400E",
    bg: "#FEF3C7",
  },
  delay: {
    Icon: Clock,
    color: "#B45309",
    bg: "#FEF3C7",
  },
  door_check: {
    Icon: CheckSquare,
    color: "#065F46",
    bg: "#D1FAE5",
  },
  signature_submitted: {
    Icon: PenTool,
    color: "#1E40AF",
    bg: "#DBEAFE",
  },
  reschedule_proposed: {
    Icon: RefreshCw,
    color: "#1E40AF",
    bg: "#DBEAFE",
  },
  other: {
    Icon: AlertCircle,
    color: "#475569",
    bg: "#F1F5F9",
  },
};

const EVENT_TYPES: EventType[] = [
  "scope_change",
  "material_request",
  "delay",
  "door_check",
  "signature_submitted",
  "reschedule_proposed",
  "other",
];

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-TW", { hour12: false });
}

function PayloadPreview({
  type,
  payload,
}: {
  type: EventType;
  payload: Record<string, unknown>;
}) {
  const t = useTranslations("components.workOrders.eventTimeline.payload");

  switch (type) {
    case "scope_change": {
      const items = Array.isArray(payload.items)
        ? (payload.items as Array<{ name?: string; quantity?: number; unit_price?: string }>)
        : [];
      return (
        <div className="text-[12px] text-[var(--text-secondary)]">
          <p className="text-[var(--text-primary)]">
            {t("reasonLabel", { value: String(payload.reason ?? "—") })}
          </p>
          {items.length > 0 && (
            <ul className="mt-1 list-disc pl-4">
              {items.map((it, i) => (
                <li key={i}>
                  {it.name} × {it.quantity}
                  {t("itemUnit", { value: String(it.unit_price ?? "") })}
                </li>
              ))}
            </ul>
          )}
          {payload.total_estimate ? (
            <p className="mt-1 font-semibold text-[#9A3412]">
              {t("totalEstimate", { value: String(payload.total_estimate) })}
            </p>
          ) : null}
        </div>
      );
    }
    case "material_request": {
      const items = Array.isArray(payload.items)
        ? (payload.items as Array<{ brand?: string; model?: string; quantity?: number }>)
        : [];
      return (
        <div className="text-[12px] text-[var(--text-secondary)]">
          <p>{t("urgencyLabel", { value: String(payload.urgency ?? "—") })}</p>
          {items.length > 0 && (
            <ul className="mt-1 list-disc pl-4">
              {items.map((it, i) => (
                <li key={i}>
                  {it.brand} {it.model} × {it.quantity}
                </li>
              ))}
            </ul>
          )}
          {payload.note ? (
            <p className="mt-1">{t("noteLabel", { value: String(payload.note) })}</p>
          ) : null}
        </div>
      );
    }
    case "delay": {
      return (
        <div className="text-[12px] text-[var(--text-secondary)]">
          <p>
            {t("delaySummary", {
              minutes: String(payload.delay_minutes ?? "—"),
              reason: String(payload.reason ?? ""),
            })}
          </p>
          {payload.reason_text ? (
            <p>{t("delayExtra", { value: String(payload.reason_text) })}</p>
          ) : null}
          <p>{t("notify", { value: String(payload.notify ?? "—") })}</p>
        </div>
      );
    }
    case "door_check": {
      const checklist = (payload.checklist ?? {}) as Record<string, boolean>;
      const checkedCount = Object.values(checklist).filter(Boolean).length;
      const totalCount = Object.keys(checklist).length;
      const photosB = Array.isArray(payload.photos_before)
        ? payload.photos_before.length
        : 0;
      const photosA = Array.isArray(payload.photos_after)
        ? payload.photos_after.length
        : 0;
      return (
        <div className="text-[12px] text-[var(--text-secondary)]">
          <p>
            {t("checkSummary", {
              checked: checkedCount,
              total: totalCount,
              before: photosB,
              after: photosA,
            })}
          </p>
          {payload.notes ? (
            <p>{t("notesLabel", { value: String(payload.notes) })}</p>
          ) : null}
        </div>
      );
    }
    default:
      // 未特別處理的事件不再直接輸出原始 payload（含 snake_case 內部欄位），改友善提示
      return (
        <span className="text-[11px] text-[var(--text-secondary)]">此事件無更多明細可顯示。</span>
      );
  }
}

interface Props {
  workOrderId: string;
}

export default function EventTimeline({ workOrderId }: Props) {
  const t = useTranslations("components.workOrders.eventTimeline");
  const tType = useTranslations("components.workOrders.eventTimeline.type");

  const typeLabels: Record<EventType, string> = useMemo(
    () => ({
      scope_change: tType("scope_change"),
      material_request: tType("material_request"),
      delay: tType("delay"),
      door_check: tType("door_check"),
      signature_submitted: tType("signature_submitted"),
      reschedule_proposed: tType("reschedule_proposed"),
      other: tType("other"),
    }),
    [tType],
  );

  const [items, setItems] = useState<WorkOrderEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<EventType | "all">("all");

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 200 };
      if (filter !== "all") query.event_type = filter;
      const res = await api.get<{ items: WorkOrderEvent[] }>(
        tenantPath(`/work-orders/${encodeURIComponent(workOrderId)}/events`),
        { query },
      );
      setItems(res.items ?? []);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  }, [workOrderId, filter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-[var(--text-secondary)]" />
          <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </h3>
          <span className="rounded bg-[#F1F5F9] px-2 py-[1px] text-[11px] text-[var(--text-secondary)]">
            {t("countSuffix", { count: items.length })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) =>
              setFilter(e.target.value as EventType | "all")
            }
            className="rounded-md border border-[var(--border)] px-2 py-1 text-[11px]"
          >
            <option value="all">{t("filterAll")}</option>
            {EVENT_TYPES.map((k) => (
              <option key={k} value={k}>
                {typeLabels[k]}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={fetchItems}
            disabled={loading}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            title={t("refresh")}
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {error}
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-[var(--text-disabled)]">
          {t("loading")}
        </div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-[var(--text-disabled)]">
          {filter === "all"
            ? t("emptyAll")
            : t("emptyFiltered", {
                label: typeLabels[filter as EventType] ?? filter,
              })}
        </div>
      ) : (
        <ol className="relative ml-3 border-l-2 border-[var(--border)]">
          {items.map((ev) => {
            const tone = TYPE_TONE[ev.event_type] ?? TYPE_TONE.other;
            const Icon = tone.Icon;
            const label = typeLabels[ev.event_type] ?? typeLabels.other;
            return (
              <li key={ev.id} className="relative mb-4 ml-4 last:mb-0">
                <span
                  className="absolute -left-[28px] flex h-6 w-6 items-center justify-center rounded-full ring-2 ring-white"
                  style={{ backgroundColor: tone.bg }}
                >
                  <Icon className="h-3 w-3" style={{ color: tone.color }} />
                </span>
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className="text-[12px] font-semibold"
                    style={{ color: tone.color }}
                  >
                    {label}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--text-disabled)]">
                    {formatTime(ev.created_at)}
                  </span>
                </div>
                <div className="mt-1">
                  <PayloadPreview type={ev.event_type} payload={ev.payload} />
                </div>
                {ev.actor_user_id && (
                  <span className="mt-1 inline-block font-mono text-[10px] text-[var(--text-disabled)]">
                    {t("byUser", { id: ev.actor_user_id.slice(0, 8) })}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
