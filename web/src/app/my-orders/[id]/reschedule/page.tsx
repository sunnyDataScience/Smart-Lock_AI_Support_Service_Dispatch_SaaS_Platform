"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  Send,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import RealtimeIndicator from "@/components/realtime/RealtimeIndicator";
import { ApiError, api } from "@/lib/api";
import { useRealtimeChannel } from "@/lib/useRealtimeChannel";
import {
  BROADCAST_CHANNELS,
  WorkOrderBroadcastEvent,
  useBroadcast,
} from "@/lib/useBroadcast";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

interface Slot {
  start?: string;
  end?: string;
  status?: "available" | "soft_conflict" | "hard_conflict";
  conflict_reason?:
    | "buffer_insufficient"
    | "another_order"
    | "customer_dnd"
    | "holiday"
    | null;
}

interface AvailabilityResponse {
  slots?: Slot[];
  customer_preferences?: {
    preferred_hours?: string[];
    dnd_hours?: string[];
  };
  past_reschedule_count?: number;
}

const MAX_PROPOSED_SLOTS = 3;
const DEFAULT_MESSAGE = "很抱歉需要調整時間，請問以下時段是否方便？";

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

function toDateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildSevenDays(start: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    d.setHours(0, 0, 0, 0);
    return d;
  });
}

function formatTime(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const REASON_LABELS: Record<NonNullable<Slot["conflict_reason"]>, string> = {
  buffer_insufficient: "鄰近工單預留時間不足",
  another_order: "已有其他工單",
  customer_dnd: "客戶勿擾時段",
  holiday: "假日",
};

export default function ReschedulePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const searchParams = useSearchParams();
  const fromHint = searchParams.get("from");

  const [wo, setWo] = useState<WorkOrder | null>(null);
  const [woLoading, setWoLoading] = useState(false);

  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [selectedDate, setSelectedDate] = useState<Date>(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });

  const [slots, setSlots] = useState<Slot[]>([]);
  const [preferredHours, setPreferredHours] = useState<string[]>([]);
  const [dndHours, setDndHours] = useState<string[]>([]);
  const [pastCount, setPastCount] = useState(0);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);

  const [proposed, setProposed] = useState<Slot[]>([]);
  const [acknowledged, setAcknowledged] = useState(false);
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [sendVia, setSendVia] = useState<"line" | "line_and_sms">("line");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitOk, setSubmitOk] = useState(false);

  const fetchWorkOrder = useCallback(async () => {
    if (!id) return;
    setWoLoading(true);
    try {
      const res = await api.get<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(id)}`,
      );
      setWo(res.data ?? null);
    } catch (e) {
      setSubmitError(formatErr(e));
    } finally {
      setWoLoading(false);
    }
  }, [id]);

  const fetchAvailability = useCallback(
    async (date: Date) => {
      if (!id) return;
      setSlotsLoading(true);
      setSlotsError(null);
      try {
        const res = await api.get<AvailabilityResponse>(
          "/api/v1/technicians/me/availability",
          {
            query: {
              work_order_id: id,
              date: toDateKey(date),
            },
          },
        );
        setSlots(res.slots ?? []);
        setPreferredHours(res.customer_preferences?.preferred_hours ?? []);
        setDndHours(res.customer_preferences?.dnd_hours ?? []);
        setPastCount(res.past_reschedule_count ?? 0);
      } catch (e) {
        setSlotsError(formatErr(e));
      } finally {
        setSlotsLoading(false);
      }
    },
    [id],
  );

  useEffect(() => {
    fetchWorkOrder();
  }, [fetchWorkOrder]);

  useEffect(() => {
    fetchAvailability(selectedDate);
  }, [fetchAvailability, selectedDate]);

  // 跨 tab 同步：同工單在其他 tab 已送出/客戶已確認時自動關閉本 tab
  const broadcast = useBroadcast<WorkOrderBroadcastEvent>(
    BROADCAST_CHANNELS.workOrder(id || "_"),
    (event) => {
      if (
        event.workOrderId === id &&
        (event.type === "reschedule_submitted" ||
          event.type === "reschedule_confirmed")
      ) {
        setSubmitOk(true);
        setTimeout(() => router.push(`/my-orders/${id}`), 1200);
      }
    },
  );

  // 訂閱該工單即時事件：客戶 RSVP 後關閉此頁
  const { status: rtStatus } = useRealtimeChannel<{
    event?: string;
    work_order?: WorkOrder;
  }>({
    channelPath: id ? `/realtime/work-orders/${id}` : "",
    enabled: !!id && !submitOk,
    onMessage: (msg) => {
      const data = (msg.payload ?? msg) as {
        event?: string;
        work_order?: WorkOrder;
      };
      if (data.event === "reschedule_confirmed_by_customer") {
        setSubmitOk(true);
        broadcast.post({ type: "reschedule_confirmed", workOrderId: id });
        setTimeout(() => router.push(`/my-orders/${id}`), 1200);
      } else if (data.event === "reschedule_rejected_by_customer") {
        setSubmitError("客戶已拒絕改期，請重新選擇時段");
      }
    },
  });

  const sevenDays = useMemo(() => buildSevenDays(weekStart), [weekStart]);

  function shiftWeek(direction: -1 | 1) {
    setWeekStart((prev) => {
      const next = new Date(prev);
      next.setDate(prev.getDate() + direction * 7);
      return next;
    });
  }

  function toggleSlot(s: Slot) {
    if (s.status === "hard_conflict") return;
    if (!s.start) return;
    setProposed((prev) => {
      const exists = prev.some((p) => p.start === s.start);
      if (exists) return prev.filter((p) => p.start !== s.start);
      if (prev.length >= MAX_PROPOSED_SLOTS) return prev;
      return [...prev, s];
    });
    if (s.status === "soft_conflict") {
      setAcknowledged(false);
    }
  }

  const hasSoftConflict = proposed.some((p) => p.status === "soft_conflict");
  const canSubmit =
    proposed.length >= 1 &&
    proposed.length <= MAX_PROPOSED_SLOTS &&
    message.trim().length >= 5 &&
    (!hasSoftConflict || acknowledged) &&
    !submitting &&
    !submitOk;

  async function submitReschedule() {
    if (!wo || !canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body = {
        proposed_slots: proposed
          .filter((p) => p.start && p.end)
          .map((p) => ({ start: p.start as string, end: p.end as string })),
        message_to_customer: message.trim(),
        send_via: sendVia,
        ...(hasSoftConflict
          ? { warning_acknowledged_at: new Date().toISOString() }
          : {}),
      };
      await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(wo.id)}/reschedule`,
        body,
      );
      setSubmitOk(true);
      broadcast.post({ type: "reschedule_submitted", workOrderId: wo.id });
      setTimeout(() => router.push(`/my-orders/${wo.id}`), 1500);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 422 && e.errorCode === "RESCHEDULE_LIMIT_EXCEEDED") {
          setSubmitError("此工單 24 小時內已改期 3 次，請聯繫客服");
        } else if (e.status === 409) {
          setSubmitError("時段或工單狀態衝突，請重新選擇");
        } else {
          setSubmitError(formatErr(e));
        }
      } else {
        setSubmitError(formatErr(e));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <TechShell>
      {/* wo_summary_header */}
      <div className="sticky top-0 z-10 flex items-start gap-2 border-b border-[var(--border)] bg-white px-2 py-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
          aria-label="返回"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex flex-1 flex-col">
          <span className="text-[11px] text-[var(--text-disabled)]">
            #{id.slice(0, 8)}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-semibold text-[var(--text-primary)]">
              改期日曆
            </span>
            <RealtimeIndicator status={rtStatus} compact />
          </div>
          {wo && (
            <span className="text-[12px] text-[var(--text-secondary)] line-clamp-1">
              {wo.address}
            </span>
          )}
          {wo?.scheduled_time && (
            <span className="mt-1 inline-flex w-fit items-center gap-1 rounded bg-[#F1F5F9] px-2 py-[2px] text-[11px] text-[var(--text-secondary)]">
              <CalendarDays className="h-3 w-3" />
              原預約：
              {new Date(wo.scheduled_time).toLocaleString("zh-TW", {
                hour12: false,
              })}
            </span>
          )}
        </div>
      </div>

      {fromHint && (
        <div className="m-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[12px] text-blue-700">
          來源：
          {fromHint === "delay"
            ? "T7 延遲通知"
            : fromHint === "no_show"
              ? "Flow 11 客戶不在場"
              : fromHint === "staff_assist"
                ? "派工人工介入協助"
                : fromHint}
        </div>
      )}

      {submitOk && (
        <div className="m-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          改期請求已送出，等候客戶確認
        </div>
      )}

      {/* customer_availability_hint */}
      {(preferredHours.length > 0 || dndHours.length > 0 || pastCount > 0) && (
        <section className="mx-4 mt-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-3 shadow-sm">
          <span className="text-[11px] font-medium text-[var(--text-secondary)]">
            客戶資訊提示
          </span>
          {preferredHours.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 text-[12px]">
              <span className="text-[var(--text-secondary)]">客戶偏好：</span>
              {preferredHours.map((h) => (
                <span
                  key={h}
                  className="rounded bg-[#D1FAE5] px-2 py-[1px] text-[#065F46]"
                >
                  {h}
                </span>
              ))}
            </div>
          )}
          {dndHours.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 text-[12px]">
              <span className="text-[var(--text-secondary)]">勿擾：</span>
              {dndHours.map((h) => (
                <span
                  key={h}
                  className="rounded bg-[#FEE2E2] px-2 py-[1px] text-[#991B1B]"
                >
                  {h}
                </span>
              ))}
            </div>
          )}
          {pastCount > 0 && (
            <div
              className={`text-[12px] ${
                pastCount >= 2
                  ? "text-amber-700 font-semibold"
                  : "text-[var(--text-secondary)]"
              }`}
            >
              此工單已改期 {pastCount} 次
              {pastCount >= 2 && "（建議與客戶協調確認，避免再次調整）"}
            </div>
          )}
        </section>
      )}

      {/* calendar_view: 7 日水平 strip */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            選擇日期
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => shiftWeek(-1)}
              className="rounded-md border border-[var(--border)] px-2 py-1 text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            >
              上一週
            </button>
            <button
              type="button"
              onClick={() => shiftWeek(1)}
              className="rounded-md border border-[var(--border)] px-2 py-1 text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
            >
              下一週
            </button>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {sevenDays.map((d) => {
            const isSelected = toDateKey(d) === toDateKey(selectedDate);
            const isToday = toDateKey(d) === toDateKey(new Date());
            const weekday = d.toLocaleDateString("zh-TW", { weekday: "short" });
            return (
              <button
                key={d.getTime()}
                type="button"
                onClick={() => setSelectedDate(d)}
                className={`flex flex-shrink-0 flex-col items-center justify-center rounded-lg border px-3 py-2 transition ${
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                    : isToday
                      ? "border-[var(--primary)] bg-white text-[var(--primary)]"
                      : "border-[var(--border)] bg-white text-[var(--text-primary)]"
                }`}
                style={{ minWidth: 60 }}
              >
                <span className="text-[11px]">{weekday}</span>
                <span className="text-[18px] font-bold">{d.getDate()}</span>
                <span className="text-[10px] opacity-80">
                  {d.getMonth() + 1} 月
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* time_slot_picker */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            時段（30 分鐘）
          </span>
          <span className="text-[11px] text-[var(--text-disabled)]">
            可選 1-{MAX_PROPOSED_SLOTS} 個備選（已選 {proposed.length}）
          </span>
        </div>

        {slotsError && (
          <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {slotsError}
          </div>
        )}

        {slotsLoading ? (
          <div className="flex h-32 items-center justify-center text-[12px] text-[var(--text-secondary)]">
            載入時段中…
          </div>
        ) : slots.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center gap-1 text-[var(--text-secondary)]">
            <AlertCircle className="h-6 w-6 text-[var(--text-disabled)]" />
            <p className="text-[12px]">此日期無可用時段</p>
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-2">
            {slots.map((s, i) => {
              const isSelected = proposed.some((p) => p.start === s.start);
              const isHard = s.status === "hard_conflict";
              const isSoft = s.status === "soft_conflict";
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => toggleSlot(s)}
                  disabled={isHard}
                  className={`relative h-12 rounded-md border text-[13px] font-medium transition ${
                    isSelected
                      ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                      : isHard
                        ? "border-[var(--border)] bg-[#F1F5F9] text-[var(--text-disabled)] cursor-not-allowed"
                        : isSoft
                          ? "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100"
                          : "border-[var(--border)] bg-white text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                  }`}
                  title={
                    s.conflict_reason
                      ? REASON_LABELS[s.conflict_reason]
                      : undefined
                  }
                >
                  {formatTime(s.start)}
                  {isSoft && (
                    <span className="absolute right-1 top-1">
                      <AlertTriangle className="h-3 w-3" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* conflict_warning */}
      {hasSoftConflict && (
        <section className="mx-4 mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 shadow-sm">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-[2px] h-4 w-4 flex-shrink-0 text-amber-600" />
            <div className="flex-1 text-[12px] text-amber-900">
              <p className="font-semibold">所選時段有 soft conflict</p>
              <ul className="mt-1 list-disc pl-4">
                {proposed
                  .filter((p) => p.status === "soft_conflict")
                  .map((p, i) => (
                    <li key={i}>
                      {formatTime(p.start)}：
                      {p.conflict_reason
                        ? REASON_LABELS[p.conflict_reason]
                        : "鄰近時段過密"}
                    </li>
                  ))}
              </ul>
              <label className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={acknowledged}
                  onChange={(e) => setAcknowledged(e.target.checked)}
                  className="h-4 w-4 accent-amber-600"
                />
                我已了解並仍要使用這些時段
              </label>
            </div>
          </div>
        </section>
      )}

      {/* customer_notification_preview */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-3 shadow-sm">
        <span className="mb-1 block text-[13px] font-semibold text-[var(--text-primary)]">
          給客戶的訊息
        </span>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
          maxLength={300}
          className="w-full rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
        />
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-secondary)]">
          <span>送出方式：</span>
          {(["line", "line_and_sms"] as const).map((v) => (
            <label key={v} className="flex items-center gap-1">
              <input
                type="radio"
                checked={sendVia === v}
                onChange={() => setSendVia(v)}
                className="h-3 w-3 accent-[var(--primary)]"
              />
              {v === "line" ? "LINE" : "LINE + SMS"}
            </label>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-[var(--text-disabled)]">
          將提供 {proposed.length} 個備選時段給客戶
        </p>
      </section>

      {submitError && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {submitError}
        </div>
      )}

      {/* action_bar */}
      <div className="sticky bottom-14 mt-4 flex items-center gap-2 border-t border-[var(--border)] bg-white px-4 py-3">
        <Link
          href={`/my-orders/${id}`}
          className="flex h-11 flex-1 items-center justify-center rounded-md border border-[var(--border)] text-[14px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
        >
          取消
        </Link>
        <button
          type="button"
          onClick={submitReschedule}
          disabled={!canSubmit}
          className="flex h-11 flex-[2] items-center justify-center gap-1 rounded-md bg-[var(--primary)] text-[14px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
        >
          <Send className="h-4 w-4" />
          {submitting ? "送出中…" : "送出改期請求"}
        </button>
      </div>

      {/* spacer for bottom nav */}
      <div className="h-2" />

      {!wo && !woLoading && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          找不到工單
        </div>
      )}
    </TechShell>
  );
}
