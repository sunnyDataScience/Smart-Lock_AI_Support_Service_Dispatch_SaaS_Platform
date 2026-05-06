"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckSquare,
  Clock,
  PackageSearch,
  PenTool,
  RefreshCw,
  Wrench,
} from "lucide-react";
import { ApiError, api } from "@/lib/api";

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

const TYPE_META: Record<
  EventType,
  {
    label: string;
    Icon: React.ComponentType<{
      className?: string;
      style?: React.CSSProperties;
    }>;
    color: string;
    bg: string;
  }
> = {
  scope_change: {
    label: "範圍變更",
    Icon: Wrench,
    color: "#9A3412",
    bg: "#FFEDD5",
  },
  material_request: {
    label: "缺料回報",
    Icon: PackageSearch,
    color: "#92400E",
    bg: "#FEF3C7",
  },
  delay: {
    label: "延遲通知",
    Icon: Clock,
    color: "#B45309",
    bg: "#FEF3C7",
  },
  door_check: {
    label: "門面檢核",
    Icon: CheckSquare,
    color: "#065F46",
    bg: "#D1FAE5",
  },
  signature_submitted: {
    label: "電子簽章",
    Icon: PenTool,
    color: "#1E40AF",
    bg: "#DBEAFE",
  },
  reschedule_proposed: {
    label: "改期請求",
    Icon: RefreshCw,
    color: "#1E40AF",
    bg: "#DBEAFE",
  },
  other: {
    label: "其他",
    Icon: AlertCircle,
    color: "#475569",
    bg: "#F1F5F9",
  },
};

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
  switch (type) {
    case "scope_change": {
      const items = Array.isArray(payload.items)
        ? (payload.items as Array<{ name?: string; quantity?: number; unit_price?: string }>)
        : [];
      return (
        <div className="text-[12px] text-[var(--text-secondary)]">
          <p className="text-[var(--text-primary)]">
            理由：{String(payload.reason ?? "—")}
          </p>
          {items.length > 0 && (
            <ul className="mt-1 list-disc pl-4">
              {items.map((it, i) => (
                <li key={i}>
                  {it.name} × {it.quantity}（單價 ${it.unit_price}）
                </li>
              ))}
            </ul>
          )}
          {payload.total_estimate ? (
            <p className="mt-1 font-semibold text-[#9A3412]">
              預估追加：${String(payload.total_estimate)}
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
          <p>急迫度：{String(payload.urgency ?? "—")}</p>
          {items.length > 0 && (
            <ul className="mt-1 list-disc pl-4">
              {items.map((it, i) => (
                <li key={i}>
                  {it.brand} {it.model} × {it.quantity}
                </li>
              ))}
            </ul>
          )}
          {payload.note ? <p className="mt-1">備註：{String(payload.note)}</p> : null}
        </div>
      );
    }
    case "delay": {
      return (
        <div className="text-[12px] text-[var(--text-secondary)]">
          <p>
            延遲 {String(payload.delay_minutes ?? "—")} 分鐘 ·{" "}
            {String(payload.reason ?? "")}
          </p>
          {payload.reason_text ? (
            <p>補充：{String(payload.reason_text)}</p>
          ) : null}
          <p>通知：{String(payload.notify ?? "—")}</p>
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
            檢核 {checkedCount}/{totalCount} · 照片 前 {photosB}/後 {photosA}
          </p>
          {payload.notes ? <p>備註：{String(payload.notes)}</p> : null}
        </div>
      );
    }
    default:
      return (
        <pre className="overflow-auto rounded bg-[#F1F5F9] p-2 text-[11px] text-[var(--text-secondary)]">
          {JSON.stringify(payload, null, 2)}
        </pre>
      );
  }
}

interface Props {
  workOrderId: string;
}

export default function EventTimeline({ workOrderId }: Props) {
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
        `/api/v1/work-orders/${encodeURIComponent(workOrderId)}/events`,
        { query },
      );
      setItems(res.items ?? []);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
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
            事件時間軸
          </h3>
          <span className="rounded bg-[#F1F5F9] px-2 py-[1px] text-[11px] text-[var(--text-secondary)]">
            {items.length} 筆
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
            <option value="all">全部類型</option>
            {Object.entries(TYPE_META).map(([k, m]) => (
              <option key={k} value={k}>
                {m.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={fetchItems}
            disabled={loading}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            title="重新整理"
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
          載入中…
        </div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-[var(--text-disabled)]">
          {filter === "all"
            ? "此工單尚無 subflow 事件紀錄"
            : `無 ${TYPE_META[filter as EventType]?.label ?? filter} 類型事件`}
        </div>
      ) : (
        <ol className="relative ml-3 border-l-2 border-[var(--border)]">
          {items.map((ev) => {
            const meta = TYPE_META[ev.event_type] ?? TYPE_META.other;
            const Icon = meta.Icon;
            return (
              <li key={ev.id} className="relative mb-4 ml-4 last:mb-0">
                <span
                  className="absolute -left-[28px] flex h-6 w-6 items-center justify-center rounded-full ring-2 ring-white"
                  style={{ backgroundColor: meta.bg }}
                >
                  <Icon className="h-3 w-3" style={{ color: meta.color }} />
                </span>
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className="text-[12px] font-semibold"
                    style={{ color: meta.color }}
                  >
                    {meta.label}
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
                    by user #{ev.actor_user_id.slice(0, 8)}
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
