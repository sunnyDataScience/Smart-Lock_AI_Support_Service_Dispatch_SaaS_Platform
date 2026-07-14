"use client";

import { use, useEffect, useState } from "react";
import {
  ChevronLeft,
  Copy,
  FileText,
  ChevronDown,
  Images,
  ExternalLink,
  Lock,
  ClipboardCheck,
  TriangleAlert,
  Info,
  CheckCircle2,
  X,
  UserPlus,
  Flag,
  Star,
  PenLine,
  Upload,
  CalendarClock,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import { UAT_HIDE_FAKE_FLOWS } from "@/lib/uatFlags";
import WorkOrderDetailSidebar from "@/components/work-orders/WorkOrderDetailSidebar";
import DispatchOrderView from "@/components/work-orders/DispatchOrderView";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  URGENCY_TONE,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, getCurrentSession, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
// 後端 detail model 將 function_tests 宣告為 list[dict]（api/models/generated.py），
// 實際回傳形狀＝_FunctionTestResult（key + pass/fail/na）——map 前縮窄用
type FunctionTestResult = components["schemas"]["_FunctionTestResult"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];
type WorkOrderAssignRequest = components["schemas"]["WorkOrderAssignRequest"];
type AssignReasonCode = WorkOrderAssignRequest["reason_code"];

// Cancellation 6-stage v2（ADR-0102 / FR-0052）— spec generated.ts 重生前的本地型別。
type CancellationResult = {
  work_order_id: string;
  cancellation_stage: string;
  customer_fee: number;
  travel_fee: number;
  technician_penalty: number | null;
  reason_code: string;
  audit_event_id: string;
};

type CancelInitiatorRole = "customer" | "customer_service" | "technician" | "system_auto";

type CancelPayload = {
  reasonCode: string;
  initiatorRole: CancelInitiatorRole;
  goodwillWaiver: boolean;
  approver: string;
  note: string;
};

// 客服可選的 reason code（覆寫專用 goodwill_waiver/supervisor_override 不在此清單）。
const CANCEL_REASON_CODES = [
  "quote_not_confirmed",
  "quote_confirmed_no_dispatch",
  "dispatched_not_departed",
  "en_route_cancelled",
  "customer_not_onsite",
  "onsite_not_executed",
  "customer_refused",
  "partial_completed_cancel",
  "technician_initiated_cancel",
  "unpaid_no_response",
  "business_cancel",
] as const;

const CANCEL_INITIATOR_ROLES: CancelInitiatorRole[] = [
  "customer_service",
  "customer",
  "technician",
  "system_auto",
];
type WorkOrderEscalateRequest = components["schemas"]["WorkOrderEscalateRequest"];
type EscalateLevel = WorkOrderEscalateRequest["level"];
type WorkOrderConfirmRequest = components["schemas"]["WorkOrderConfirmRequest"];
type SignaturePayload = components["schemas"]["SignaturePayload"];
type ApiResponseGeneric = components["schemas"]["ApiResponseGeneric"];
type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardEnvelope = components["schemas"]["ProblemCardEnvelope"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];
type Message = components["schemas"]["Message"];
type MessagePage = components["schemas"]["MessagePage"];
type Technician = components["schemas"]["Technician"];

const ACCEPT_FROM: ReadonlySet<WorkOrderStatus> = new Set(["assigned"]);
const ASSIGN_FROM: ReadonlySet<WorkOrderStatus> = new Set(["inquiring", "assigned"]);
// Flow 8 reassign — accepted/in_progress 階段強制改派（不破壞 wo_id）
const REASSIGN_FROM: ReadonlySet<WorkOrderStatus> = new Set(["accepted", "in_progress"]);
const COMPLETE_FROM: ReadonlySet<WorkOrderStatus> = new Set(["accepted", "in_progress"]);
const CANCEL_FROM: ReadonlySet<WorkOrderStatus> = new Set([
  "inquiring",
  "qualified",
  "quoted",
  "negotiating",
  "accepted",
  "scheduled",
  "dispatching",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
]);
const ESCALATE_FROM: ReadonlySet<WorkOrderStatus> = new Set([
  "inquiring",
  "qualified",
  "quoted",
  "negotiating",
  "accepted",
  "scheduled",
  "dispatching",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
]);
const CONFIRM_FROM: ReadonlySet<WorkOrderStatus> = new Set(["completed"]);
const SIGNATURE_FROM: ReadonlySet<WorkOrderStatus> = new Set([
  "accepted",
  "scheduled",
  "dispatching",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
  "completed",
]);
// 改期：對齊後端 _RESCHEDULE_FROM（assigned | accepted | in_progress）
const RESCHEDULE_FROM: ReadonlySet<WorkOrderStatus> = new Set([
  "assigned",
  "scheduled",
  "dispatching",
  "en_route",
  "arrived",
  "accepted",
  "in_progress",
]);

const ESCALATE_LEVEL_VALUES: readonly EscalateLevel[] = [
  "operations_manager",
  "tenant_admin",
];

const ASSIGN_REASON_VALUES: readonly AssignReasonCode[] = [
  "auto_dispatch_exhausted",
  "customer_requested_specific_tech",
  "skill_shortage_override",
  "sla_rescue",
  "other",
];

const PC_STATUS_TONE: Record<
  ProblemCardStatus,
  { color: string; bg: string }
> = {
  draft: { color: "#6366F1", bg: "#EEF2FF" },
  confirmed: { color: "#3B82F6", bg: "#DBEAFE" },
  resolved: { color: "#10B981", bg: "#D1FAE5" },
};

/* ── SLA Timeline（由 order.status + 時間戳衍生，非寫死）──────── */

// 工單「操作流程」狀態排序（cancelled 另計為 -1）。
// 注意：WorkOrder API status 實際只用 7 值（由後端 7 值 DB enum 對映：
//   created→inquiring / assigned / accepted / in_progress / completed / confirmed→closed / cancelled）。
// 操作順序為 建立 → 派工(assigned) → 技師接受(accepted) → 施工中 → 完工 → 結案(closed)。
// 不可用完整報價列舉排序（那裡 accepted=客戶接受報價，排在 assigned 之前，會把「派工中」
// 誤顯示為「已接受」）。
const STATUS_RANK: Record<string, number> = {
  inquiring: 0, // DB created：已建立、未派工
  assigned: 1, // 派工給技師（待技師接受）
  accepted: 2, // 技師已接受
  in_progress: 3, // 施工中
  completed: 4, // 完工（待客戶確認）
  closed: 5, // 客戶確認結案
};

// 6 個 SLA 節點 → 抵達該階段所需的最低 status rank + 對應的真實時間欄位。
const SLA_STAGES: ReadonlyArray<{
  key: string;
  threshold: number;
  timeField?: keyof WorkOrder;
}> = [
  { key: "created", threshold: 0, timeField: "created_at" }, // inquiring
  { key: "dispatched", threshold: 1, timeField: "scheduled_time" }, // assigned
  { key: "accepted", threshold: 2 }, // accepted（accepted_at 未上 envelope，無時間）
  { key: "inProgress", threshold: 3, timeField: "actual_arrival" }, // in_progress
  { key: "completed", threshold: 4, timeField: "completion_time" }, // completed
  { key: "confirmed", threshold: 5 }, // closed
];

/** 緊湊時間格式 MM/DD HH:mm（SLA 節點下方小字用）。 */
function slaTimeShort(iso?: string | null): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}/${dd} ${hh}:${mi}`;
}

function SlaTimeline({ order }: { order: WorkOrder | null }) {
  const t = useTranslations("pages.workOrderDetail.sla");
  if (!order) return null;

  const isCancelled = order.status === "cancelled";
  const rank = STATUS_RANK[order.status] ?? -1;
  const fullyDone = rank >= STATUS_RANK.closed; // 已結案 → 全綠
  // 已抵達的最高節點 index（決定 active 與進度條）。
  const lastReached = Math.max(
    0,
    ...SLA_STAGES.map((s, i) => (rank >= s.threshold ? i : -1)),
  );
  const pct = isCancelled
    ? 0
    : fullyDone
      ? 100
      : Math.round((lastReached / (SLA_STAGES.length - 1)) * 100);

  // CR-0100：SLA 倒數/逾時（用 computed sla_deadline；終態不顯示倒數）。
  const slaBadge = (() => {
    const terminal = [
      "completed",
      "billed",
      "paid",
      "closed",
      "cancelled",
    ].includes(order.status);
    if (terminal || !order.sla_deadline) return null;
    const ms = new Date(order.sla_deadline).getTime();
    if (Number.isNaN(ms)) return null;
    const diff = ms - Date.now();
    const overdue = diff < 0;
    const mins = Math.floor(Math.abs(diff) / 60000);
    const dur = `${Math.floor(mins / 60)}h${String(mins % 60).padStart(2, "0")}m`;
    return {
      overdue,
      label: overdue ? t("overdue", { time: dur }) : t("remaining", { time: dur }),
    };
  })();

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-[var(--bg-page)] p-3">
      <div className="flex items-center justify-between">
        {SLA_STAGES.map((s, i) => {
          // 取消：僅「建立」算完成，其餘 pending。
          const done = isCancelled
            ? i === 0
            : fullyDone
              ? i <= lastReached
              : i < lastReached;
          const active = !isCancelled && !fullyDone && i === lastReached;
          const rawTime = s.timeField
            ? (order[s.timeField] as string | null | undefined)
            : undefined;
          const time = slaTimeShort(rawTime);
          return (
            <div key={s.key} className="flex flex-col items-center gap-1">
              {active ? (
                <div className="h-4 w-4 rounded-full border-[3px] border-[var(--primary)] bg-white" />
              ) : done ? (
                <div className="h-3 w-3 rounded-full bg-[var(--success)]" />
              ) : (
                <div className="h-3 w-3 rounded-full border-[1.5px] border-[#CBD5E1] bg-white" />
              )}
              <span
                className={`text-[11px] ${active ? "font-semibold text-[var(--primary)]" : "text-[var(--text-secondary)]"}`}
              >
                {t(`stage.${s.key}`)}
              </span>
              {time && (
                <span className="text-[10px] text-[var(--text-disabled)]">
                  {time}
                </span>
              )}
            </div>
          );
        })}
      </div>
      {slaBadge && (
        <div className="flex justify-end">
          <span
            className={`text-[12px] font-semibold ${slaBadge.overdue ? "text-[var(--error)]" : "text-[var(--warning)]"}`}
          >
            {slaBadge.label}
          </span>
        </div>
      )}
      <div className="h-2 w-full rounded bg-[var(--border)]">
        <div
          className="h-2 rounded bg-[var(--primary)] transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ── Problem Card Summary ─────────────────────────── */

function ProblemCardSummary({
  pcId,
  onLoaded,
}: {
  pcId?: string;
  onLoaded?: (card: ProblemCard | null) => void;
}) {
  const t = useTranslations("pages.workOrderDetail.pcSummary");
  const tCommon = useTranslations("common");
  const tUrgency = useTranslations("urgency");
  const [card, setCard] = useState<ProblemCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pcId) {
      onLoaded?.(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCard(null);
    (async () => {
      try {
        const res = await api.get<ProblemCardEnvelope>(
          tenantPath(`/problem-cards/${encodeURIComponent(pcId)}`),
        );
        if (cancelled) return;
        const data = res.data ?? null;
        setCard(data);
        onLoaded?.(data);
      } catch (e) {
        if (cancelled) return;
        setError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pcId, onLoaded]);

  const pcTone = card ? PC_STATUS_TONE[card.status] : null;
  const pcUrgencyTone = card ? URGENCY_TONE[card.urgency] : null;
  const dash = tCommon("notAvailable");

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center gap-3">
        <FileText className="h-5 w-5 text-[var(--primary)]" />
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </span>
        <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[12px] text-[var(--primary)]">
          {t("badge")}
        </span>
        {pcId && (
          <Link
            href={`/problem-cards/${pcId}`}
            className="ml-auto font-mono text-[12px] font-medium text-[var(--primary)] hover:underline"
            title={pcId}
          >
            {pcId.slice(0, 8)} →
          </Link>
        )}
      </div>

      {!pcId && (
        <span className="text-[13px] text-[var(--text-disabled)]">
          {t("noPc")}
        </span>
      )}
      {error && (
        <span className="text-[13px] text-red-600">
          {t("loadFailed", { error })}
        </span>
      )}
      {loading && !card && (
        <span className="text-[13px] text-[var(--text-disabled)]">
          {t("loading")}
        </span>
      )}

      {card && (
        <>
          <div className="flex items-center gap-2">
            {pcTone && (
              <span
                className="rounded-full px-3 py-1 text-[12px] font-semibold"
                style={{ color: pcTone.color, backgroundColor: pcTone.bg }}
              >
                {t(`status.${card.status}`)}
              </span>
            )}
            {pcUrgencyTone && (
              <span
                className="rounded px-2 py-1 text-[11px] font-medium"
                style={{ color: pcUrgencyTone.color, backgroundColor: pcUrgencyTone.bg }}
              >
                {t("urgencyLabel", { label: tUrgency(card.urgency) })}
              </span>
            )}
            {card.confidence_score != null && (
              <span className="text-[12px] text-[var(--text-secondary)]">
                {t("aiConfidence", {
                  percent: (card.confidence_score * 100).toFixed(0),
                })}
              </span>
            )}
          </div>

          <div className="grid grid-cols-4 gap-2">
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t("field.brand")}
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {card.brand || dash}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t("field.model")}
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {card.model || dash}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t("field.category")}
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {card.category || dash}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t("field.conversation")}
              </span>
              <Link
                href={`/conversations/${card.conversation_id}`}
                className="font-mono text-[13px] font-semibold text-[var(--primary)] hover:underline"
                title={card.conversation_id}
              >
                {card.conversation_id.slice(0, 8)}
              </Link>
            </div>
          </div>

          <div className="rounded-lg bg-[#F8FAFC] p-3">
            <span className="block text-[11px] text-[var(--text-secondary)]">
              {t("field.symptom")}
            </span>
            <p className="mt-1 text-[13px] leading-[1.6] text-[var(--text-primary)]">
              {card.symptom || dash}
            </p>
          </div>
        </>
      )}
    </div>
  );
}

/* ── LINE Media Gallery (real) ───────────────────── */

function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}/${mm}/${dd} ${hh}:${mi}`;
}

function LineMediaGallery({ conversationId }: { conversationId?: string }) {
  const t = useTranslations("pages.workOrderDetail.media");
  const [items, setItems] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setItems([]);
    (async () => {
      try {
        const res = await api.get<MessagePage>(
          tenantPath(`/conversations/${encodeURIComponent(conversationId)}/messages`),
          { query: { limit: 100 } },
        );
        if (cancelled) return;
        const all = (res.items ?? []) as Message[];
        const media = all.filter(
          (m) => !!m.media_url && (m.type === "image" || m.type === "video"),
        );
        setItems(media);
      } catch (e) {
        if (cancelled) return;
        setError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Images className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
          <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[11px] font-semibold text-[var(--primary)]">
            {t("badge")}
          </span>
          {items.length > 0 && (
            <span className="text-[12px] text-[var(--text-secondary)]">
              {t("count", { count: items.length })}
            </span>
          )}
        </div>
      </div>

      {!conversationId && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("noConversation")}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {t("loadFailed", { error })}
        </div>
      )}

      {conversationId && loading && items.length === 0 && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("loading")}
        </div>
      )}

      {conversationId && !loading && items.length === 0 && !error && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("empty")}
        </div>
      )}

      {items.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {items.map((m) => (
            <a
              key={m.id}
              href={m.media_url ?? undefined}
              target="_blank"
              rel="noreferrer"
              className="group flex flex-col gap-1"
              title={t("submittedAt", { time: formatDateTime(m.created_at) })}
            >
              <div className="relative h-[128px] w-[128px] overflow-hidden rounded-lg border border-[var(--border)] bg-[#F1F5F9]">
                {m.type === "image" ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={m.media_url ?? ""}
                    alt={t("imageAlt")}
                    loading="lazy"
                    decoding="async"
                    className="h-full w-full object-cover transition-transform group-hover:scale-[1.03]"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[12px] text-[var(--text-secondary)]">
                    {t("videoLabel")}
                  </div>
                )}
              </div>
              <span className="text-[11px] text-[var(--text-disabled)]">
                {formatDateTime(m.created_at)}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Work Timeline (real, from WorkOrder timestamps) ─── */

type BadgeKind = "system" | "technician" | "schedule" | "complete";
type TimelineEventKey =
  | "created"
  | "scheduled"
  | "arrived"
  | "completed"
  | "lastUpdated";

interface TimelineEvent {
  color: string;
  badge: BadgeKind;
  eventKey: TimelineEventKey;
  detailKey?: "createdFromPc" | "scheduledWithTech" | "scheduledNoTech" | "lastUpdatedDetail";
  detailParams?: Record<string, string | number>;
  time: string | null | undefined;
}

const BADGE_TONE: Record<BadgeKind, { textColor: string; bg: string }> = {
  system: { textColor: "#64748B", bg: "#F1F5F9" },
  technician: { textColor: "#1E40AF", bg: "#DBEAFE" },
  schedule: { textColor: "#9F1239", bg: "#FFE4E6" },
  complete: { textColor: "#065F46", bg: "#D1FAE5" },
};

const EVENT_TITLE_KEY: Record<TimelineEventKey, string> = {
  created: "created",
  scheduled: "scheduledTitle",
  arrived: "arrivedTitle",
  completed: "completedTitle",
  lastUpdated: "lastUpdatedTitle",
};

function buildEvents(order: WorkOrder | null): TimelineEvent[] {
  if (!order) return [];
  const list: TimelineEvent[] = [];

  list.push({
    color: "#94A3B8",
    badge: "system",
    eventKey: "created",
    detailKey: order.problem_card_id ? "createdFromPc" : undefined,
    detailParams: order.problem_card_id
      ? { shortId: order.problem_card_id.slice(0, 8) }
      : undefined,
    time: order.created_at,
  });

  if (order.scheduled_time) {
    list.push({
      color: "#F43F5E",
      badge: "schedule",
      eventKey: "scheduled",
      detailKey: order.technician_id ? "scheduledWithTech" : "scheduledNoTech",
      detailParams: order.technician_id
        ? { shortId: order.technician_id.slice(0, 8) }
        : undefined,
      time: order.scheduled_time,
    });
  }

  if (order.actual_arrival) {
    list.push({
      color: "#3B82F6",
      badge: "technician",
      eventKey: "arrived",
      time: order.actual_arrival,
    });
  }

  if (order.completion_time) {
    list.push({
      color: "#10B981",
      badge: "complete",
      eventKey: "completed",
      time: order.completion_time,
    });
  }

  if (order.updated_at && order.updated_at !== order.created_at) {
    list.push({
      color: "#94A3B8",
      badge: "system",
      eventKey: "lastUpdated",
      detailKey: "lastUpdatedDetail",
      detailParams: { status: order.status },
      time: order.updated_at,
    });
  }

  return list.sort((a, b) => {
    const ta = a.time ? new Date(a.time).getTime() : 0;
    const tb = b.time ? new Date(b.time).getTime() : 0;
    return tb - ta;
  });
}

function WorkTimeline({ order }: { order: WorkOrder | null }) {
  const t = useTranslations("pages.workOrderDetail.timeline");
  const tCommon = useTranslations("common");
  const events = buildEvents(order);
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </span>
        {/* UAT 隱藏(20260702 決議 7):時間軸篩選為未實作的 disabled 死鈕 */}
        {!UAT_HIDE_FAKE_FLOWS && (
          <button
            disabled
            title={tCommon("comingSoon")}
            className="flex items-center gap-[6px] rounded-md border border-[var(--border)] px-3 py-[6px] opacity-60"
          >
            <span className="text-[13px] text-[var(--text-secondary)]">{t("filterAll")}</span>
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
          </button>
        )}
      </div>

      {events.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("empty")}
        </div>
      ) : (
        <div className="relative">
          <div className="absolute bottom-0 left-[5px] top-[6px] w-[2px] bg-[var(--border)]" />
          <div className="flex flex-col gap-5">
            {events.map((ev, i) => {
              const tone = BADGE_TONE[ev.badge];
              const detail = ev.detailKey
                ? t(`event.${ev.detailKey}`, ev.detailParams ?? {})
                : null;
              return (
                <div key={i} className="flex gap-4 pt-[2px]">
                  <div
                    className="relative z-10 mt-[2px] h-3 w-3 flex-shrink-0 rounded-full"
                    style={{ backgroundColor: ev.color }}
                  />
                  <div className="flex flex-col gap-1">
                    <span
                      className="inline-flex w-fit rounded px-2 py-[2px] text-[11px]"
                      style={{ color: tone.textColor, backgroundColor: tone.bg }}
                    >
                      {t(`badge.${ev.badge}`)}
                    </span>
                    <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                      {t(`event.${EVENT_TITLE_KEY[ev.eventKey]}`)}
                    </span>
                    {detail && (
                      <span className="text-[12px] text-[var(--text-secondary)]">
                        {detail}
                      </span>
                    )}
                    <span className="text-[11px] text-[var(--text-disabled)]">
                      {formatDateTime(ev.time)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Conversation Thread (mock) ──────────────────── */

/** 對話角色 → 氣泡樣式（user=客人左、assistant=客服/AI 右、system=系統置中）。 */
function _roleLabel(
  role: Message["role"],
  t: ReturnType<typeof useTranslations>,
): string {
  if (role === "user") return t("roleCustomer");
  if (role === "assistant") return t("roleAgent");
  return t("roleSystem");
}

function ConversationThread({ conversationId }: { conversationId?: string }) {
  const t = useTranslations("pages.workOrderDetail.conversation");
  const [items, setItems] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setItems([]);
    (async () => {
      try {
        const res = await api.get<MessagePage>(
          tenantPath(`/conversations/${encodeURIComponent(conversationId)}/messages`),
          { query: { limit: 100 } },
        );
        if (cancelled) return;
        // API 依 created_at DESC 回傳；逐字稿需正序（舊→新）顯示。
        const all = ((res.items ?? []) as Message[]).slice().reverse();
        setItems(all);
      } catch (e) {
        if (cancelled) return;
        setError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          {t("title")}
        </span>
        {conversationId && (
          <a
            href={`/conversations/${encodeURIComponent(conversationId)}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-[6px] hover:opacity-80"
          >
            <span className="text-[13px] text-[var(--primary)]">{t("openInNewWindow")}</span>
            <ExternalLink className="h-[14px] w-[14px] text-[var(--primary)]" />
          </a>
        )}
      </div>

      {!conversationId && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("noConversation")}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {t("loadFailed", { error })}
        </div>
      )}

      {conversationId && loading && items.length === 0 && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("loading")}
        </div>
      )}

      {conversationId && !loading && items.length === 0 && !error && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          {t("empty")}
        </div>
      )}

      {items.length > 0 && (
        <div className="flex max-h-[420px] flex-col gap-3 overflow-y-auto rounded-lg bg-[var(--bg-page)] p-4">
          {items.map((m) => {
            if (m.role === "system") {
              return (
                <div key={m.id} className="flex justify-center">
                  <span className="rounded-full bg-[#E2E8F0] px-3 py-1 text-[11px] text-[var(--text-secondary)]">
                    {m.content}
                  </span>
                </div>
              );
            }
            const isCustomer = m.role === "user";
            return (
              <div
                key={m.id}
                className={`flex flex-col gap-1 ${isCustomer ? "items-start" : "items-end"}`}
              >
                <span className="text-[11px] text-[var(--text-secondary)]">
                  {_roleLabel(m.role, t)}・{formatDateTime(m.created_at)}
                </span>
                <div
                  className={`max-w-[78%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-[13px] leading-[1.6] ${
                    isCustomer
                      ? "rounded-tl-sm bg-white text-[var(--text-primary)] border border-[var(--border)]"
                      : "rounded-tr-sm bg-[var(--primary)] text-white"
                  }`}
                >
                  {m.content}
                  {m.media_url && (
                    <a
                      href={m.media_url}
                      target="_blank"
                      rel="noreferrer"
                      className={`mt-1 block text-[12px] underline ${isCustomer ? "text-[var(--primary)]" : "text-white"}`}
                    >
                      {t("attachment")}
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex items-center justify-center gap-[6px] rounded-b-lg bg-[#F1F5F9] px-4 py-2">
        <Lock className="h-3 w-3 text-[var(--text-disabled)]" />
        <span className="text-[12px] text-[var(--text-disabled)]">
          {t("readOnlyNotice")}
        </span>
      </div>
    </div>
  );
}

/* ── Completion Report（接 order，真實完工資料）─────────────────
   註：功能測試逐項結果（指紋/密碼/電池）需後端先補結構化欄位（service_report
   增 function_tests），屬 B 類全端工，待 CIA。此處先呈現真實的完工時間/摘要/
   實收金額，未完工則誠實顯示空狀態，不再顯示寫死的假測試結果。 */

// CR-0100 功能測試測項中文標籤（後端存 key，前端顯示；對齊技師端勾選清單）。
const FUNCTION_TEST_LABEL: Record<string, string> = {
  fingerprint: "指紋解鎖",
  password: "密碼解鎖",
  card: "卡片(RFID)",
  app: "App/藍牙",
  mechanical_key: "機械鑰匙",
  battery: "電池電壓",
};

const FUNCTION_TEST_RESULT_STYLE: Record<string, { symbol: string; color: string }> = {
  pass: { symbol: "✓", color: "var(--success)" },
  fail: { symbol: "✗", color: "var(--error)" },
  na: { symbol: "—", color: "var(--text-disabled)" },
};

// M05 Q052 六段完工細狀態中文標籤（後端存 key；與 DispatchOrderView/WorkOrderDetailSidebar 對齊）
const COMPLETION_STATUS_LABEL: Record<string, string> = {
  pending_report: "待完工回報",
  pending_photos: "待照片",
  pending_customer_confirm: "待客戶確認",
  pending_cs_review: "待客服審核",
  completed: "已完工",
  closed: "已結案",
};

// 歷史資料的 completion_summary 可能是機器字串（[ONSITE_COMPLETE] sig=.. photos=[..] notes=..）；
// 解析成人話：notes 原文＋「已簽名・完工照片 N 張」註記。新完工後端已改存乾淨 notes，此為防禦。
function parseCompletionSummary(raw: string): { text: string | null; meta: string | null } {
  const m = raw.match(
    /^\[ONSITE_COMPLETE\]\s+sig=(\S+)\s+photos=\[([^\]]*)\](?:\s+notes=([\s\S]*))?$/,
  );
  if (!m) return { text: raw, meta: null };
  const photoCount = m[2] ? m[2].split(",").filter(Boolean).length : 0;
  const metaParts: string[] = [];
  if (m[1]) metaParts.push("已簽名");
  metaParts.push(`完工照片 ${photoCount} 張`);
  return { text: m[3]?.trim() || null, meta: metaParts.join("・") };
}

function CompletionReport({ order }: { order: WorkOrder | null }) {
  const t = useTranslations("pages.workOrderDetail.completion");
  if (!order) return null;
  const done =
    !!order.completion_time ||
    ["completed", "billed", "paid", "closed"].includes(order.status);
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-[var(--success)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>
        {done && order.completion_time && (
          <span className="text-[12px] text-[var(--text-secondary)]">
            {t("submittedAt", { time: formatDateTime(order.completion_time) })}
          </span>
        )}
      </div>
      {!done ? (
        <div className="flex h-16 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
          <span className="text-[13px] text-[var(--text-disabled)]">
            {t("notCompleted")}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {order.completion_status && (
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
                {t("statusLabel")}
              </span>
              <span className="text-[13px] text-[var(--text-primary)]">
                {COMPLETION_STATUS_LABEL[order.completion_status] ?? order.completion_status}
              </span>
            </div>
          )}
          {order.customer_final_amount != null && (
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
                {t("finalAmountLabel")}
              </span>
              <span className="text-[14px] font-bold text-[var(--text-primary)]">
                ${order.customer_final_amount}
              </span>
            </div>
          )}
          {/* CR-0100 施工摘要（completion_summary，技師 notes 抽出；歷史機器字串前端解析） */}
          {(() => {
            const parsed = order.completion_summary?.trim()
              ? parseCompletionSummary(order.completion_summary.trim())
              : { text: null, meta: null };
            return (
              <div className="flex flex-col gap-1">
                <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
                  {t("summaryLabel")}
                </span>
                <p className="whitespace-pre-wrap text-[13px] text-[var(--text-primary)]">
                  {parsed.text ?? t("noSummary")}
                </p>
                {parsed.meta && (
                  <span className="text-[12px] text-[var(--text-disabled)]">
                    {parsed.meta}
                  </span>
                )}
              </div>
            );
          })()}
          {/* CR-0100 功能測試逐項結果 */}
          {order.function_tests && order.function_tests.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
                {t("functionTestsLabel")}
              </span>
              <div className="flex flex-col gap-[6px]">
                {(order.function_tests as FunctionTestResult[]).map((ft) => {
                  const style =
                    FUNCTION_TEST_RESULT_STYLE[ft.result] ??
                    FUNCTION_TEST_RESULT_STYLE.na;
                  return (
                    <div
                      key={ft.key}
                      className="flex items-center gap-2 text-[13px]"
                    >
                      <span
                        className="w-4 text-center font-bold"
                        style={{ color: style.color }}
                      >
                        {style.symbol}
                      </span>
                      <span className="text-[var(--text-primary)]">
                        {FUNCTION_TEST_LABEL[ft.key] ?? ft.key}
                      </span>
                      <span className="text-[12px] text-[var(--text-disabled)]">
                        {t(`testResult.${ft.result}`)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Exception Records（接 work_order_id，撈 M15 exception-cases）──── */

type ExceptionCaseItem = {
  id: string;
  exception_type: string;
  status: string;
  severity: string;
  description: string | null;
  created_at: string | null;
};

// 例外案件狀態中文標籤（exception_service 值域；原本 {it.status} 直出英文原始碼）
const EXCEPTION_STATUS_LABEL: Record<string, string> = {
  open: "待處理",
  investigating: "調查中",
  escalated: "已升級",
  resolved: "已解決",
  closed: "已結案",
};

const EXCEPTION_TYPE_LABEL: Record<string, string> = {
  no_show: "放鴿子",
  customer_absent: "客戶不在",
  scope_change_rejected: "加價拒絕",
  material_shortage: "缺料",
  delay_severe: "嚴重延遲",
  appearance_refused: "拒絕施工",
  payment_failed: "付款失敗",
  quality_complaint: "品質客訴",
  schedule_conflict: "排班衝突",
  other: "其他",
};

const EXCEPTION_SEVERITY_COLOR: Record<string, string> = {
  critical: "var(--error)",
  high: "var(--error)",
  medium: "var(--warning)",
  low: "var(--text-secondary)",
};

function ExceptionRecords({ workOrderId }: { workOrderId?: string }) {
  const t = useTranslations("pages.workOrderDetail.exception");
  const [items, setItems] = useState<ExceptionCaseItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!workOrderId) return;
    let cancelled = false;
    setLoading(true);
    api
      .get<{ items: ExceptionCaseItem[] }>(tenantPath("/exception-cases"), {
        query: { work_order_id: workOrderId },
      })
      .then((res) => {
        if (!cancelled) setItems(res.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workOrderId]);

  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TriangleAlert className="h-5 w-5 text-[var(--error)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>
      </div>
      {loading ? (
        <div className="flex h-16 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
          <span className="text-[13px] text-[var(--text-disabled)]">
            {t("loading")}
          </span>
        </div>
      ) : items.length === 0 ? (
        <div className="flex h-16 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
          <span className="text-[13px] text-[var(--text-disabled)]">
            {t("empty")}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((it) => (
            <div
              key={it.id}
              className="flex items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2"
            >
              <span
                className="mt-[6px] h-2 w-2 flex-shrink-0 rounded-full"
                style={{
                  backgroundColor:
                    EXCEPTION_SEVERITY_COLOR[it.severity] ??
                    "var(--text-secondary)",
                }}
              />
              <div className="flex flex-1 flex-col gap-[2px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    {EXCEPTION_TYPE_LABEL[it.exception_type] ??
                      it.exception_type}
                  </span>
                  <span className="text-[11px] text-[var(--text-disabled)]">
                    {EXCEPTION_STATUS_LABEL[it.status] ?? it.status}
                  </span>
                </div>
                {it.description && (
                  <span className="text-[12px] text-[var(--text-secondary)]">
                    {it.description}
                  </span>
                )}
                <span className="text-[11px] text-[var(--text-disabled)]">
                  {formatDateTime(it.created_at)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────── */

interface PageProps {
  params: Promise<{ id: string }>;
}

type ActionMode =
  | "complete"
  | "cancel"
  | "assign"
  | "escalate"
  | "confirm"
  | "signature"
  | "reschedule"
  | "requestReschedule"
  | "notifyDelay"
  | "materialRequest"
  | null;
type ActionPending =
  | "accept"
  | "complete"
  | "cancel"
  | "assign"
  | "escalate"
  | "confirm"
  | "signature"
  | "reschedule"
  | "requestReschedule"
  | "notifyDelay"
  | "materialRequest"
  | null;

export default function WorkOrderDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const t = useTranslations("pages.workOrderDetail");
  const tHeader = useTranslations("pages.workOrderDetail.header");
  const tActions = useTranslations("pages.workOrderDetail.actions");
  const tToast = useTranslations("pages.workOrderDetail.toast");
  const tCancelDialog = useTranslations("pages.workOrderDetail.cancelDialog");
  const tLoading = useTranslations("pages.workOrderDetail.loading");
  const tCommon = useTranslations("common");
  const tGroup = useTranslations("status.workOrderGroup");
  const tUrgency = useTranslations("urgency");
  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [problemCard, setProblemCard] = useState<ProblemCard | null>(null);
  const [actionMode, setActionMode] = useState<ActionMode>(null);
  const [actionPending, setActionPending] = useState<ActionPending>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionToast, setActionToast] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        // 全 cutover：一律 tenant-scoped v2（tenantPath 由 auth.getTenantId() 解析）
        const res = await api.get<WorkOrderEnvelope>(
          tenantPath(`/work-orders/${encodeURIComponent(id)}`),
        );
        if (!cancelled) setOrder(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const formatActionError = (e: unknown): string =>
    friendlyError(e);

  const handleAccept = async () => {
    setActionPending("accept");
    setActionError(null);
    try {
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}:accept`),
      );
      setOrder(res.data ?? null);
      setActionToast(tToast("accepted"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleComplete = async (summary: string, actualAmount: string | null) => {
    setActionPending("complete");
    setActionError(null);
    try {
      const body: Record<string, unknown> = { summary, photos_before: [], photos_after: [] };
      if (actualAmount) body.actual_amount = actualAmount;
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}:complete`),
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast(tToast("completed"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleCancel = async (payload: CancelPayload) => {
    setActionPending("cancel");
    setActionError(null);
    try {
      // spec-aligned tenant-scoped 端點 + SoD headers（ADR-0102 / FR-0052）
      const session = getCurrentSession();
      const tenantId = session?.tenantId;
      if (!tenantId) {
        throw new ApiError(400, { error_code: "NO_TENANT", message: "Missing tenant" });
      }
      const res = await api.post<{ data: CancellationResult }>(
        `/tenants/${encodeURIComponent(tenantId)}/work-orders/${encodeURIComponent(id)}/cancel`,
        {
          reason_code: payload.reasonCode,
          initiator_role: payload.initiatorRole,
          goodwill_waiver: payload.goodwillWaiver,
          note: payload.note || undefined,
        },
        {
          headers: {
            "X-Initiator": session?.userId ?? "operator",
            "X-Approver": payload.approver,
          },
        },
      );
      const r = res.data;
      // 端點回 CancellationResult（非 WorkOrder）→ 本地標記工單為 cancelled
      setOrder((prev) => (prev ? { ...prev, status: "cancelled" } : prev));
      setActionMode(null);
      setActionToast(
        tCancelDialog("feeResult", {
          stage: r.cancellation_stage,
          customerFee: r.customer_fee,
          travelFee: r.travel_fee,
        }),
      );
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleAssign = async (
    technicianId: string,
    reasonCode: AssignReasonCode,
    reasonText: string,
  ) => {
    setActionPending("assign");
    setActionError(null);
    try {
      // Flow 8 reassign — accepted/in_progress 走 :reassign（不破壞 wo_id，
      // backend force-back status to 'assigned'）；其他狀態走 :assign。
      const isReassign = order ? REASSIGN_FROM.has(order.status) : false;
      let res: WorkOrderEnvelope;
      if (isReassign) {
        // :reassign body 需 technician_id + reason 必填（min_length=1）
        const reason = reasonText.trim() || "強制改派（admin override）";
        res = await api.post<WorkOrderEnvelope>(
          tenantPath(`/work-orders/${encodeURIComponent(id)}:reassign`),
          { technician_id: technicianId, reason },
        );
      } else {
        const body: Record<string, unknown> = {
          technician_id: technicianId,
          reason_code: reasonCode,
        };
        if (reasonText) body.reason_text = reasonText;
        res = await api.post<WorkOrderEnvelope>(
          tenantPath(`/work-orders/${encodeURIComponent(id)}:assign`),
          body,
        );
      }
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast(tToast("assigned"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleConfirm = async (rating: number, feedback: string) => {
    setActionPending("confirm");
    setActionError(null);
    try {
      const body: WorkOrderConfirmRequest = { rating };
      if (feedback) body.feedback = feedback;
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}:confirm`),
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast(tToast("confirmed"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleSignature = async (
    customerSignature: string,
    technicianSignature: string,
    gpsLat: number | null,
    gpsLng: number | null,
  ) => {
    setActionPending("signature");
    setActionError(null);
    try {
      const body: SignaturePayload = {
        customer_signature: customerSignature,
        technician_signature: technicianSignature,
        signed_at: new Date().toISOString(),
      };
      if (gpsLat != null) body.gps_lat = gpsLat;
      if (gpsLng != null) body.gps_lng = gpsLng;
      const res = await api.post<ApiResponseGeneric>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/signature`),
        body,
      );
      setActionMode(null);
      setActionToast(res.message || tToast("signatureDone"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleEscalate = async (level: EscalateLevel, reason: string) => {
    setActionPending("escalate");
    setActionError(null);
    try {
      const body: WorkOrderEscalateRequest = { level, reason };
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(id)}:escalate`),
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      const tone =
        level === "operations_manager"
          ? tToast("escalatedOps")
          : tToast("escalatedTenant");
      setActionToast(tone);
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleReschedule = async (
    slots: Array<{ start: string; end: string }>,
    message: string,
    sendVia: "line" | "line_and_sms",
  ) => {
    setActionPending("reschedule");
    setActionError(null);
    try {
      // CR-0007（2026-06-04 業主拍 §8 全 5 HD）：
      //   多時段提案改走 v2 :propose；slots 1-3（HD-02）；寫 saas.reschedule_proposal（HD-04）
      //   返回值是 proposal 紀錄（非更新後的 work_order）— scheduled_at 不變，待客戶 RSVP 後變
      // send_via 暫把 "line_and_sms" 映射到 "line"（v2 schema 只接 line|sms|email；
      // 雙通道送由後端 LINE Push 配置處理）。TODO 待 send_via 完整 contract 對齊
      const v2SendVia = sendVia === "line_and_sms" ? "line" : sendVia;
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(id)}/reschedule:propose`),
        {
          proposed_slots: slots,
          message_to_customer: message,
          send_via: v2SendVia,
        },
      );
      setActionMode(null);
      setActionToast(tToast("rescheduleSent", { count: slots.length }));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  // --- Operational v2 handlers（tenant-scoped v2 endpoints, CR-0003 P2-W4） ---

  const handleRequestReschedule = async (newScheduledAt: string, reason: string) => {
    setActionPending("requestReschedule");
    setActionError(null);
    try {
      const session = getCurrentSession();
      const tenantId = session?.tenantId;
      if (!tenantId) {
        throw new ApiError(400, { error_code: "NO_TENANT", message: "Missing tenant" });
      }
      await api.post(
        `/tenants/${encodeURIComponent(tenantId)}/work-orders/${encodeURIComponent(id)}/reschedule-request`,
        { new_scheduled_at: newScheduledAt, reason },
      );
      // service 回傳 dict（非 WorkOrder envelope），重新 fetch 最新 WO
      const res = await api.get<WorkOrderEnvelope>(
        `/tenants/${encodeURIComponent(tenantId)}/work-orders/${encodeURIComponent(id)}`,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast(tToast("requestRescheduleSent"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleNotifyDelay = async (delayMinutes: number, reason: string) => {
    setActionPending("notifyDelay");
    setActionError(null);
    try {
      const session = getCurrentSession();
      const tenantId = session?.tenantId;
      if (!tenantId) {
        throw new ApiError(400, { error_code: "NO_TENANT", message: "Missing tenant" });
      }
      await api.post(
        `/tenants/${encodeURIComponent(tenantId)}/work-orders/${encodeURIComponent(id)}/notify-delay`,
        { delay_minutes: delayMinutes, reason },
      );
      setActionMode(null);
      setActionToast(tToast("notifyDelaySent", { minutes: delayMinutes }));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleMaterialRequest = async (
    items: Array<{ brand: string; model: string; quantity: number }>,
    urgency: "now" | "today" | "tomorrow",
    note: string,
  ) => {
    setActionPending("materialRequest");
    setActionError(null);
    try {
      const session = getCurrentSession();
      const tenantId = session?.tenantId;
      if (!tenantId) {
        throw new ApiError(400, { error_code: "NO_TENANT", message: "Missing tenant" });
      }
      const body: Record<string, unknown> = { items, urgency };
      if (note) body.note = note;
      const res = await api.post<WorkOrderEnvelope>(
        `/tenants/${encodeURIComponent(tenantId)}/work-orders/${encodeURIComponent(id)}/material-request`,
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast(tToast("materialRequestSent"));
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  useEffect(() => {
    if (!actionToast) return;
    const t = setTimeout(() => setActionToast(null), 2400);
    return () => clearTimeout(t);
  }, [actionToast]);

  const shortId = id.slice(0, 8);
  const displayId = order?.document_number ?? shortId;
  const statusGroup = order ? STATUS_GROUP_MAP[order.status] : null;
  const statusTone = statusGroup ? STATUS_GROUP_TONE[statusGroup] : null;
  const urgencyTone = order ? URGENCY_TONE[order.urgency] : null;
  const dash = tCommon("notAvailable");
  const districtAddr = order
    ? order.district && !order.address.startsWith(order.district)
      ? `${order.district} · ${order.address}`
      : order.address || dash
    : dash;

  const canAccept = order ? ACCEPT_FROM.has(order.status) : false;
  // Flow 8 — assign 按鈕同時涵蓋原 :assign (inquiring/assigned) 與
  // :reassign (accepted/in_progress) 兩條路徑；handleAssign 內以
  // REASSIGN_FROM 判斷實際 endpoint。
  const canAssign = order
    ? ASSIGN_FROM.has(order.status) || REASSIGN_FROM.has(order.status)
    : false;
  const canComplete = order ? COMPLETE_FROM.has(order.status) : false;
  const canCancel = order ? CANCEL_FROM.has(order.status) : false;
  const canEscalate = order ? ESCALATE_FROM.has(order.status) : false;
  const canConfirm = order ? CONFIRM_FROM.has(order.status) : false;
  const canSignature = order ? SIGNATURE_FROM.has(order.status) : false;
  const canReschedule = order ? RESCHEDULE_FROM.has(order.status) : false;
  const anyAction =
    canAccept ||
    canAssign ||
    canComplete ||
    canCancel ||
    canEscalate ||
    canConfirm ||
    canSignature ||
    canReschedule;
  const assignLabel = order?.technician_id
    ? tActions("reassign")
    : tActions("assign");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-auto">
          {/* Detail Header */}
          <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
            <span className="text-[11px] text-[var(--text-secondary)]">
              {tHeader("breadcrumb", { shortId: displayId })}
            </span>
            <div className="flex items-center gap-3">
              <Link
                href="/work-orders"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--bg-page)]"
              >
                <ChevronLeft className="h-5 w-5 text-[var(--text-secondary)]" />
              </Link>
              <span className="font-mono text-[28px] font-bold text-[var(--text-primary)]" title={id}>
                {displayId}
              </span>
              {statusTone && statusGroup && (
                <span
                  className="rounded px-2 py-1 text-[14px] font-semibold"
                  style={{ color: statusTone.color, backgroundColor: statusTone.bg }}
                >
                  {tGroup(statusGroup)}
                </span>
              )}
              {urgencyTone && order && (
                <span
                  className="rounded px-2 py-1 text-[12px] font-medium"
                  style={{ color: urgencyTone.color, backgroundColor: urgencyTone.bg }}
                >
                  {tHeader("urgencyLabel", { label: tUrgency(order.urgency) })}
                </span>
              )}
              <Copy className="h-4 w-4 text-[var(--text-secondary)]" />
            </div>
            {order && (
              <div className="flex flex-wrap items-center gap-4 text-[13px] text-[var(--text-secondary)]">
                <span>
                  {tHeader("brandLabel")}
                  <span className="font-medium text-[var(--text-primary)]">{order.brand || dash}</span>
                </span>
                <span>
                  {tHeader("modelLabel")}
                  <span className="font-medium text-[var(--text-primary)]">{order.model || dash}</span>
                </span>
                <span>
                  {tHeader("addressLabel")}
                  <span className="font-medium text-[var(--text-primary)]">{districtAddr}</span>
                </span>
                {order.problem_card_id && (
                  <Link
                    href={`/problem-cards/${order.problem_card_id}`}
                    className="font-mono text-[var(--primary)] hover:underline"
                  >
                    {tHeader("linkedProblemCard", {
                      shortId: order.problem_card_id.slice(0, 8),
                    })}
                  </Link>
                )}
              </div>
            )}
            <SlaTimeline order={order} />

            {anyAction && (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {canAccept && (
                  <button
                    onClick={handleAccept}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    {actionPending === "accept"
                      ? tActions("accepting")
                      : tActions("accept")}
                  </button>
                )}
                {canAssign && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("assign");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[var(--primary)] bg-white px-4 py-2 text-[13px] font-semibold text-[var(--primary)] transition hover:bg-[var(--primary-light)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <UserPlus className="h-4 w-4" />
                    {assignLabel}
                  </button>
                )}
                {canComplete && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("complete");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <ClipboardCheck className="h-4 w-4" />
                    {tActions("complete")}
                  </button>
                )}
                {canCancel && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("cancel");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-semibold text-[var(--error)] transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <X className="h-4 w-4" />
                    {tActions("cancel")}
                  </button>
                )}
                {canConfirm && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("confirm");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md bg-[#0EA5E9] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Star className="h-4 w-4" />
                    {tActions("confirmClose")}
                  </button>
                )}
                {canEscalate && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("escalate");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[#F59E0B] bg-white px-4 py-2 text-[13px] font-semibold text-[#B45309] transition hover:bg-[#FEF3C7] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Flag className="h-4 w-4" />
                    {tActions("escalate")}
                  </button>
                )}
                {canSignature && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("signature");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[#7C3AED] bg-white px-4 py-2 text-[13px] font-semibold text-[#7C3AED] transition hover:bg-[#F5F3FF] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <PenLine className="h-4 w-4" />
                    {tActions("signature")}
                  </button>
                )}
                {canReschedule && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("reschedule");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[#0EA5E9] bg-white px-4 py-2 text-[13px] font-semibold text-[#0369A1] transition hover:bg-[#F0F9FF] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CalendarClock className="h-4 w-4" />
                    {tActions("reschedule")}
                  </button>
                )}
                {/* CR-0003 P2-W4 — ops v2 actions */}
                {canReschedule && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setActionMode("requestReschedule");
                    }}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md border border-[#6366F1] bg-white px-4 py-2 text-[13px] font-semibold text-[#4338CA] transition hover:bg-[#EEF2FF] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CalendarClock className="h-4 w-4" />
                    {tActions("requestReschedule")}
                  </button>
                )}
                <button
                  onClick={() => {
                    setActionError(null);
                    setActionMode("notifyDelay");
                  }}
                  disabled={actionPending !== null}
                  className="inline-flex items-center gap-2 rounded-md border border-[#F59E0B] bg-white px-4 py-2 text-[13px] font-semibold text-[#92400E] transition hover:bg-[#FEF3C7] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <TriangleAlert className="h-4 w-4" />
                  {tActions("notifyDelay")}
                </button>
                <button
                  onClick={() => {
                    setActionError(null);
                    setActionMode("materialRequest");
                  }}
                  disabled={actionPending !== null}
                  className="inline-flex items-center gap-2 rounded-md border border-[#10B981] bg-white px-4 py-2 text-[13px] font-semibold text-[#065F46] transition hover:bg-[#D1FAE5] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Upload className="h-4 w-4" />
                  {tActions("materialRequest")}
                </button>
              </div>
            )}

            {actionError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {tActions("actionFailed", { error: actionError })}
              </div>
            )}
          </div>

          {error && (
            <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {tLoading("loadFailed", { error })}
            </div>
          )}

          {loading && !order && (
            <div className="mx-8 mt-4 text-[13px] text-[var(--text-secondary)]">
              {tLoading("loadingOrder")}
            </div>
          )}

          {/* UAT 隱藏(20260702 決議 7):banner 唯一提及的「設備面板示意」已隨面板一併
              隱藏,頁面所有可見區塊皆為即時資料 → banner 無存在必要,恢復顯示時一起回來 */}
          {!UAT_HIDE_FAKE_FLOWS && (
            <div className="mx-8 my-4 flex items-start gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3">
              <Info className="mt-[2px] h-4 w-4 flex-shrink-0 text-[#64748B]" />
              <span className="text-[13px] leading-[1.6] text-[#475569]">
                {t("info.banner")}
              </span>
            </div>
          )}

          {order && (
            <div className="mx-8 mt-4 flex justify-end">
              <Link
                href={`/admin/quotes?wo=${order.id}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-md border border-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-[var(--primary)] transition hover:bg-[var(--primary-light)]"
              >
                <FileText className="h-4 w-4" />
                {t("quoteCta")}
              </Link>
            </div>
          )}

          <DispatchOrderView order={order} onUpdated={setOrder} />

          <ProblemCardSummary
            pcId={order?.problem_card_id}
            onLoaded={setProblemCard}
          />
          <LineMediaGallery conversationId={problemCard?.conversation_id} />
          <WorkTimeline order={order} />
          <ConversationThread conversationId={problemCard?.conversation_id ?? undefined} />
          <CompletionReport order={order} />
          <ExceptionRecords workOrderId={order?.id} />
        </div>

        <WorkOrderDetailSidebar
          workOrder={order ?? undefined}
          conversationId={problemCard?.conversation_id ?? undefined}
        />
      </div>

      {actionMode === "complete" && (
        <CompleteModal
          pending={actionPending === "complete"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleComplete}
        />
      )}

      {actionMode === "cancel" && (
        <CancelModal
          pending={actionPending === "cancel"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleCancel}
        />
      )}

      {actionMode === "assign" && (
        <AssignModal
          pending={actionPending === "assign"}
          workOrderId={id}
          currentTechnicianId={order?.technician_id ?? null}
          onCancel={() => setActionMode(null)}
          onSubmit={handleAssign}
        />
      )}

      {actionMode === "escalate" && (
        <EscalateModal
          pending={actionPending === "escalate"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleEscalate}
        />
      )}

      {actionMode === "confirm" && (
        <ConfirmModal
          pending={actionPending === "confirm"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleConfirm}
        />
      )}

      {actionMode === "signature" && (
        <SignatureModal
          pending={actionPending === "signature"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleSignature}
        />
      )}

      {actionMode === "reschedule" && (
        <RescheduleModal
          pending={actionPending === "reschedule"}
          currentScheduled={order?.scheduled_time ?? null}
          onCancel={() => setActionMode(null)}
          onSubmit={handleReschedule}
        />
      )}

      {actionMode === "requestReschedule" && (
        <RequestRescheduleModal
          pending={actionPending === "requestReschedule"}
          currentScheduled={order?.scheduled_time ?? null}
          onCancel={() => setActionMode(null)}
          onSubmit={handleRequestReschedule}
        />
      )}

      {actionMode === "notifyDelay" && (
        <NotifyDelayModal
          pending={actionPending === "notifyDelay"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleNotifyDelay}
        />
      )}

      {actionMode === "materialRequest" && (
        <MaterialRequestModal
          pending={actionPending === "materialRequest"}
          onCancel={() => setActionMode(null)}
          onSubmit={handleMaterialRequest}
        />
      )}

      {actionToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white shadow-lg">
          {actionToast}
        </div>
      )}
    </div>
  );
}

/* ── Action Modals ───────────────────────────────── */

function CompleteModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (summary: string, actualAmount: string | null) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.completeDialog");
  const [summary, setSummary] = useState("");
  const [actualAmount, setActualAmount] = useState("");
  const trimmed = summary.trim();
  const amountValid = actualAmount === "" || /^-?\d+(\.\d{1,2})?$/.test(actualAmount.trim());
  const canSubmit = trimmed.length > 0 && amountValid && !pending;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-[var(--success)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("summaryLabel")} <span className="text-[var(--error)]">{t("summaryRequired")}</span>
            </label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={4}
              maxLength={2000}
              placeholder={t("summaryPlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {t("summaryCounter", { current: trimmed.length })}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("amountLabel")}
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={actualAmount}
              onChange={(e) => setActualAmount(e.target.value)}
              placeholder={t("amountPlaceholder")}
              className={`rounded-md border px-3 py-2 text-[13px] focus:outline-none ${
                amountValid
                  ? "border-[var(--border)] focus:border-[var(--primary)]"
                  : "border-red-300 focus:border-red-400"
              }`}
            />
            {!amountValid && (
              <span className="text-[11px] text-red-600">
                {t("amountInvalid")}
              </span>
            )}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={() => onSubmit(trimmed, actualAmount.trim() || null)}
            disabled={!canSubmit}
            className="rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface CandidateItem {
  technician: Technician;
  score: number;
  distance_km?: number | null;
  skill_match?: number | null;
  availability_eta_minutes?: number | null;
}

interface CandidatesResponse {
  candidates: CandidateItem[];
  total: number;
  auto_dispatch_attempts?: unknown[];
}

function AssignModal({
  pending,
  workOrderId,
  currentTechnicianId,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  workOrderId: string;
  currentTechnicianId: string | null;
  onCancel: () => void;
  onSubmit: (
    technicianId: string,
    reasonCode: AssignReasonCode,
    reasonText: string,
  ) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.assignDialog");
  const tCommon = useTranslations("common");
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [techsLoading, setTechsLoading] = useState(true);
  const [techsError, setTechsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [reasonCode, setReasonCode] = useState<AssignReasonCode>(
    "auto_dispatch_exhausted",
  );
  const [reasonText, setReasonText] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<CandidatesResponse>(
          tenantPath("/dispatch:candidates"),
          { query: { work_order_id: workOrderId } },
        );
        if (cancelled) return;
        const items = res.candidates ?? [];
        setCandidates(items);
        const initial = items.find((c) => c.technician.id !== currentTechnicianId);
        if (initial) setSelected(initial.technician.id);
      } catch (e) {
        if (cancelled) return;
        setTechsError(
          friendlyError(e),
        );
      } finally {
        if (!cancelled) setTechsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workOrderId, currentTechnicianId]);

  const canSubmit = selected !== "" && !pending;

  const scoreColor = (score: number) =>
    score >= 70 ? "#10B981" : score >= 40 ? "#F59E0B" : "#94A3B8";
  const formatDistance = (km: number | null | undefined): string => {
    if (km == null) return tCommon("notAvailable");
    if (km === 0) return t("distanceInArea");
    return t("distanceKm", { km });
  };
  const formatEta = (min: number | null | undefined): string =>
    min == null ? tCommon("notAvailable") : t("etaMinutes", { min });

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[640px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {currentTechnicianId ? t("titleReassign") : t("titleAssign")}
          </span>
          <span className="ml-auto text-[11px] text-[var(--text-disabled)]">
            {t("scoreFormula")}
          </span>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("candidateLabel")} <span className="text-[var(--error)]">{t("required")}</span>
            </label>
            {techsLoading ? (
              <div className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] text-[var(--text-disabled)]">
                {t("loadingCandidates")}
              </div>
            ) : techsError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {t("loadFailed", { error: techsError })}
              </div>
            ) : candidates.length === 0 ? (
              <div className="rounded-md border border-dashed border-[var(--border)] px-3 py-2 text-[13px] text-[var(--text-disabled)]">
                {t("noCandidates")}
              </div>
            ) : (
              <div className="flex max-h-[320px] flex-col gap-2 overflow-y-auto pr-1">
                {candidates.map((c) => {
                  const tech = c.technician;
                  const active = selected === tech.id;
                  const isCurrent = tech.id === currentTechnicianId;
                  return (
                    <button
                      key={tech.id}
                      type="button"
                      onClick={() => setSelected(tech.id)}
                      className={`flex flex-col gap-1 rounded-lg border px-3 py-2 text-left transition ${
                        active
                          ? "border-[var(--primary)] bg-[var(--primary-light)]"
                          : "border-[var(--border)] bg-white hover:bg-[var(--bg-page)]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                          {tech.name}
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)]">
                          {tech.phone}
                        </span>
                        {isCurrent && (
                          <span className="rounded bg-[#FEF3C7] px-2 py-[1px] text-[10px] font-medium text-[#92400E]">
                            {t("currentlyAssigned")}
                          </span>
                        )}
                        <span
                          className="ml-auto rounded px-2 py-[2px] text-[12px] font-bold text-white"
                          style={{ backgroundColor: scoreColor(c.score) }}
                          title={t("scoreTooltip")}
                        >
                          {c.score.toFixed(1)}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--text-secondary)]">
                        <span>
                          {t("skillPercent", {
                            percent: ((c.skill_match ?? 0) * 100).toFixed(0),
                          })}
                        </span>
                        <span>
                          {t("distance", { value: formatDistance(c.distance_km) })}
                        </span>
                        <span>
                          {t("rating", { rating: tech.rating.toFixed(1) })}
                        </span>
                        <span>{formatEta(c.availability_eta_minutes)}</span>
                        {tech.skills.length > 0 && (
                          <span title={tech.skills.join(", ")}>
                            {t("skillsPrefix", {
                              names:
                                tech.skills.slice(0, 2).join("、") +
                                (tech.skills.length > 2 ? t("skillsMore") : ""),
                            })}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("reasonLabel")} <span className="text-[var(--error)]">{t("required")}</span>
            </label>
            <select
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value as AssignReasonCode)}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            >
              {ASSIGN_REASON_VALUES.map((value) => (
                <option key={value} value={value}>
                  {t(`reason.${value}`)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("reasonTextLabel")}
            </label>
            <textarea
              value={reasonText}
              onChange={(e) => setReasonText(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder={t("reasonTextPlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {t("reasonTextCounter", { current: reasonText.trim().length })}
            </span>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            onClick={() => onSubmit(selected, reasonCode, reasonText.trim())}
            disabled={!canSubmit}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

function CancelModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (payload: CancelPayload) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.cancelDialog");
  const [reasonCode, setReasonCode] = useState<string>(CANCEL_REASON_CODES[2]); // dispatched_not_departed
  const [initiatorRole, setInitiatorRole] = useState<CancelInitiatorRole>("customer_service");
  const [goodwillWaiver, setGoodwillWaiver] = useState(false);
  const [approver, setApprover] = useState("");
  const [note, setNote] = useState("");
  const trimmedNote = note.trim();
  // SoD：X-Approver 必填且須與發起人不同（後端最終把關，前端先擋空白）
  const canSubmit = approver.trim().length > 0;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <X className="h-5 w-5 text-[var(--error)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>

        <div className="flex flex-col gap-4">
          {/* reason code 分類（決定階段 + 費用） */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("reasonCodeLabel")}
            </label>
            <select
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value)}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            >
              {CANCEL_REASON_CODES.map((code) => (
                <option key={code} value={code}>
                  {t(`reasonCodes.${code}`)}
                </option>
              ))}
            </select>
          </div>

          {/* 發起方 */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("initiatorLabel")}
            </label>
            <select
              value={initiatorRole}
              onChange={(e) => setInitiatorRole(e.target.value as CancelInitiatorRole)}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            >
              {CANCEL_INITIATOR_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`initiator.${role}`)}
                </option>
              ))}
            </select>
          </div>

          {/* SoD 覆核主管 ID（X-Approver） */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("approverLabel")}
            </label>
            <input
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder={t("approverPlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
          </div>

          {/* goodwill 豁免 */}
          <label className="flex items-center gap-2 text-[13px] text-[var(--text-primary)]">
            <input
              type="checkbox"
              checked={goodwillWaiver}
              onChange={(e) => setGoodwillWaiver(e.target.checked)}
            />
            {t("goodwillLabel")}
          </label>

          {/* 備註 */}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("reasonLabel")}
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder={t("reasonPlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {t("counter", { current: trimmedNote.length })}
            </span>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("back")}
          </button>
          <button
            onClick={() =>
              onSubmit({
                reasonCode,
                initiatorRole,
                goodwillWaiver,
                approver: approver.trim(),
                note: trimmedNote,
              })
            }
            disabled={pending || !canSubmit}
            className="rounded-md bg-[var(--error)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfirmModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (rating: number, feedback: string) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.confirmDialog");
  const [rating, setRating] = useState<number>(5);
  const [hover, setHover] = useState<number>(0);
  const [feedback, setFeedback] = useState("");
  const trimmed = feedback.trim();
  const valid = rating >= 1 && rating <= 5 && trimmed.length <= 1000;
  const display = hover > 0 ? hover : rating;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <Star className="h-5 w-5 text-[#0EA5E9]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("ratingLabel")} <span className="text-[var(--error)]">{t("required")}</span>
            </label>
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((n) => {
                const filled = n <= display;
                return (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setRating(n)}
                    onMouseEnter={() => setHover(n)}
                    onMouseLeave={() => setHover(0)}
                    className="p-1 transition"
                    aria-label={t("starAria", { n })}
                  >
                    <Star
                      className={`h-7 w-7 ${
                        filled ? "fill-[#F59E0B] text-[#F59E0B]" : "text-[#CBD5E1]"
                      }`}
                    />
                  </button>
                );
              })}
              <span className="ml-2 text-[13px] font-medium text-[var(--text-secondary)]">
                {display >= 1 && display <= 5 ? t(`ratingHint.${display}`) : ""}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              {t("feedbackLabel")}
            </label>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value.slice(0, 1000))}
              rows={4}
              placeholder={t("feedbackPlaceholder")}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#0EA5E9] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {t("counter", { current: trimmed.length })}
            </span>
          </div>
        </div>

        <p className="mt-3 rounded-md bg-[#E0F2FE] px-3 py-2 text-[12px] leading-[1.6] text-[#075985]">
          {t("warning")}
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("back")}
          </button>
          <button
            onClick={() => onSubmit(rating, trimmed)}
            disabled={pending || !valid}
            className="rounded-md bg-[#0EA5E9] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

function SignaturePadField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | null;
  onChange: (b64: string | null) => void;
}) {
  const t = useTranslations("pages.workOrderDetail.signaturePad");
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    if (!file.type.startsWith("image/")) {
      setError(t("errorImageOnly"));
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError(t("errorTooLarge"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") return;
      const comma = result.indexOf(",");
      const b64 = comma >= 0 ? result.slice(comma + 1) : result;
      onChange(b64);
    };
    reader.onerror = () => setError(t("errorReadFailed"));
    reader.readAsDataURL(file);
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-3">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">{label}</span>
      {value ? (
        <div className="flex items-center gap-3">
          <div className="flex h-[64px] w-[64px] items-center justify-center rounded border border-[var(--border)] bg-white text-[10px] text-[var(--text-disabled)]">
            {t("base64Label")}
          </div>
          <div className="flex flex-col">
            <span className="text-[12px] font-medium text-[var(--text-primary)]">
              {t("uploadedLength", { chars: value.length.toLocaleString() })}
            </span>
            <button
              type="button"
              onClick={() => onChange(null)}
              className="mt-1 self-start text-[11px] text-[var(--error)] hover:underline"
            >
              {t("clear")}
            </button>
          </div>
        </div>
      ) : (
        <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-[var(--border)] bg-white px-3 py-2 text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]">
          <Upload className="h-4 w-4" />
          {t("selectFile")}
          <input
            type="file"
            accept="image/png,image/jpeg,image/svg+xml"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = "";
            }}
          />
        </label>
      )}
      {error && <span className="text-[11px] text-[var(--error)]">{error}</span>}
    </div>
  );
}

function SignatureModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (
    customer: string,
    technician: string,
    gpsLat: number | null,
    gpsLng: number | null,
  ) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.signatureDialog");
  const [customer, setCustomer] = useState<string | null>(null);
  const [technician, setTechnician] = useState<string | null>(null);
  const [gpsLat, setGpsLat] = useState<string>("");
  const [gpsLng, setGpsLng] = useState<string>("");
  const [gpsError, setGpsError] = useState<string | null>(null);

  const valid = !!customer && !!technician;

  const captureGps = () => {
    if (!navigator.geolocation) {
      setGpsError(t("errorNoGeolocation"));
      return;
    }
    setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsLat(pos.coords.latitude.toFixed(6));
        setGpsLng(pos.coords.longitude.toFixed(6));
      },
      (err) => setGpsError(err.message || t("errorLocateFailed")),
      { timeout: 8000 },
    );
  };

  const submit = () => {
    if (!customer || !technician) return;
    const lat = gpsLat.trim() ? Number(gpsLat) : null;
    const lng = gpsLng.trim() ? Number(gpsLng) : null;
    if ((lat != null && Number.isNaN(lat)) || (lng != null && Number.isNaN(lng))) {
      setGpsError(t("errorLatLngNumeric"));
      return;
    }
    onSubmit(customer, technician, lat, lng);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[560px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <PenLine className="h-5 w-5 text-[#7C3AED]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>

        <p className="mb-3 rounded-md bg-[#F5F3FF] px-3 py-2 text-[12px] leading-[1.6] text-[#5B21B6]">
          {t("intro")}
        </p>

        <div className="flex flex-col gap-3">
          <SignaturePadField
            label={t("customerLabel")}
            value={customer}
            onChange={setCustomer}
          />
          <SignaturePadField
            label={t("technicianLabel")}
            value={technician}
            onChange={setTechnician}
          />

          <div className="rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-3">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                {t("gpsLabel")}
              </span>
              <button
                type="button"
                onClick={captureGps}
                disabled={pending}
                className="rounded-md border border-[var(--border)] bg-white px-2 py-1 text-[11px] font-medium text-[var(--primary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {t("captureGps")}
              </button>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input
                type="text"
                value={gpsLat}
                onChange={(e) => setGpsLat(e.target.value)}
                placeholder={t("latPlaceholder")}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[12px] focus:border-[#7C3AED] focus:outline-none"
              />
              <input
                type="text"
                value={gpsLng}
                onChange={(e) => setGpsLng(e.target.value)}
                placeholder={t("lngPlaceholder")}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[12px] focus:border-[#7C3AED] focus:outline-none"
              />
            </div>
            {gpsError && (
              <span className="mt-1 block text-[11px] text-[var(--error)]">
                {gpsError}
              </span>
            )}
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("back")}
          </button>
          <button
            onClick={submit}
            disabled={pending || !valid}
            className="rounded-md bg-[#7C3AED] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

function EscalateModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (level: EscalateLevel, reason: string) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.escalateDialog");
  const [level, setLevel] = useState<EscalateLevel>("operations_manager");
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 500;
  const activeLabel = t(`level.${level}.label`);

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[520px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <Flag className="h-5 w-5 text-[#B45309]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          {ESCALATE_LEVEL_VALUES.map((value) => {
            const active = value === level;
            return (
              <button
                key={value}
                onClick={() => setLevel(value)}
                className={`rounded-lg border px-3 py-3 text-left transition ${
                  active
                    ? "border-[#B45309] bg-[#FEF3C7]"
                    : "border-[var(--border)] hover:bg-[var(--bg-page)]"
                }`}
              >
                <div className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {t(`level.${value}.label`)}
                </div>
                <div className="mt-1 text-[12px] leading-[1.5] text-[var(--text-secondary)]">
                  {t(`level.${value}.hint`)}
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            {t("reasonLabel")}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 500))}
            rows={4}
            placeholder={
              activeLabel
                ? t("reasonPlaceholderActive", { label: activeLabel })
                : t("reasonPlaceholderFallback")
            }
            className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#B45309] focus:outline-none"
          />
          <span className="text-[11px] text-[var(--text-disabled)]">
            {t("counter", { current: trimmed.length })}
          </span>
        </div>

        <p className="mt-3 rounded-md bg-[#FEF3C7] px-3 py-2 text-[12px] leading-[1.6] text-[#92400E]">
          {t("warning")}
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("back")}
          </button>
          <button
            onClick={() => onSubmit(level, trimmed)}
            disabled={pending || !valid}
            className="rounded-md bg-[#B45309] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Ops v2 Modals (CR-0003 P2-W4) ──────────────────────────────── */

function RequestRescheduleModal({
  pending,
  currentScheduled,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  currentScheduled: string | null;
  onCancel: () => void;
  onSubmit: (newScheduledAt: string, reason: string) => Promise<void>;
}) {
  const base = currentScheduled ? (() => {
    const d = new Date(currentScheduled);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  })() : "";
  const [newDateTime, setNewDateTime] = useState(base);
  const [reason, setReason] = useState("");
  const trimmedReason = reason.trim();
  const valid = newDateTime.length > 0 && trimmedReason.length > 0 && trimmedReason.length <= 500 && !pending;

  const handleSubmit = () => {
    const iso = newDateTime ? new Date(newDateTime).toISOString() : "";
    if (!iso) return;
    onSubmit(iso, trimmedReason);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <CalendarClock className="h-5 w-5 text-[#4338CA]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            直接改約（通知客戶）
          </span>
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              新約定時間 <span className="text-[var(--error)]">*</span>
            </label>
            <input
              type="datetime-local"
              value={newDateTime}
              onChange={(e) => setNewDateTime(e.target.value)}
              disabled={pending}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#6366F1] focus:outline-none disabled:opacity-50"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              改期原因 <span className="text-[var(--error)]">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value.slice(0, 500))}
              rows={3}
              maxLength={500}
              placeholder="請說明改期原因（最多 500 字）"
              disabled={pending}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#6366F1] focus:outline-none disabled:opacity-50"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {trimmedReason.length} / 500
            </span>
          </div>
        </div>
        <p className="mt-3 rounded-md bg-[#EEF2FF] px-3 py-2 text-[12px] leading-[1.6] text-[#4338CA]">
          系統將立即 LINE 通知客戶新的約定時間。
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!valid}
            className="rounded-md bg-[#4338CA] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中..." : "確認改約"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NotifyDelayModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (delayMinutes: number, reason: string) => Promise<void>;
}) {
  const [delayMinutes, setDelayMinutes] = useState("15");
  const [reason, setReason] = useState("");
  const trimmedReason = reason.trim();
  const parsedMinutes = parseInt(delayMinutes, 10);
  const minutesValid = !Number.isNaN(parsedMinutes) && parsedMinutes >= 5 && parsedMinutes <= 300;
  const valid = minutesValid && trimmedReason.length > 0 && trimmedReason.length <= 500 && !pending;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <TriangleAlert className="h-5 w-5 text-[#B45309]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            通知客戶延遲
          </span>
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              延遲分鐘數（5–300）<span className="text-[var(--error)]">*</span>
            </label>
            <input
              type="number"
              min={5}
              max={300}
              value={delayMinutes}
              onChange={(e) => setDelayMinutes(e.target.value)}
              disabled={pending}
              className={`rounded-md border px-3 py-2 text-[13px] focus:outline-none disabled:opacity-50 ${
                minutesValid
                  ? "border-[var(--border)] focus:border-[#F59E0B]"
                  : "border-red-300 focus:border-red-400"
              }`}
            />
            {!minutesValid && (
              <span className="text-[11px] text-red-600">請輸入 5–300 之間的整數分鐘</span>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              延遲原因 <span className="text-[var(--error)]">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value.slice(0, 500))}
              rows={3}
              maxLength={500}
              placeholder="請說明延遲原因（最多 500 字）"
              disabled={pending}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#F59E0B] focus:outline-none disabled:opacity-50"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {trimmedReason.length} / 500
            </span>
          </div>
        </div>
        <p className="mt-3 rounded-md bg-[#FEF3C7] px-3 py-2 text-[12px] leading-[1.6] text-[#92400E]">
          系統將 LINE 通知客戶技師到場時間延遲。
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={() => valid && onSubmit(parsedMinutes, trimmedReason)}
            disabled={!valid}
            className="rounded-md bg-[#B45309] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中..." : "發送通知"}
          </button>
        </div>
      </div>
    </div>
  );
}

type MaterialUrgency = "now" | "today" | "tomorrow";

function MaterialRequestModal({
  pending,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  onCancel: () => void;
  onSubmit: (
    items: Array<{ brand: string; model: string; quantity: number }>,
    urgency: MaterialUrgency,
    note: string,
  ) => Promise<void>;
}) {
  const [items, setItems] = useState([{ brand: "", model: "", quantity: 1 }]);
  const [urgency, setUrgency] = useState<MaterialUrgency>("today");
  const [note, setNote] = useState("");

  const updateItem = (idx: number, field: "brand" | "model" | "quantity", value: string | number) => {
    setItems(items.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  };
  const addItem = () => {
    if (items.length >= 20) return;
    setItems([...items, { brand: "", model: "", quantity: 1 }]);
  };
  const removeItem = (idx: number) => {
    if (items.length <= 1) return;
    setItems(items.filter((_, i) => i !== idx));
  };

  const itemsValid = items.every(
    (it) => it.brand.trim().length > 0 && it.model.trim().length > 0 && it.quantity >= 1,
  );
  const valid = itemsValid && !pending;

  const handleSubmit = () => {
    if (!valid) return;
    onSubmit(
      items.map((it) => ({ brand: it.brand.trim(), model: it.model.trim(), quantity: it.quantity })),
      urgency,
      note.trim(),
    );
  };

  const urgencyOptions: MaterialUrgency[] = ["now", "today", "tomorrow"];
  const urgencyLabel: Record<MaterialUrgency, string> = {
    now: "立即（緊急）",
    today: "今日內",
    tomorrow: "明日前",
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[560px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <Upload className="h-5 w-5 text-[#065F46]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            缺料回報
          </span>
        </div>
        <div className="flex flex-col gap-3">
          {items.map((it, idx) => (
            <div key={idx} className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[12px] font-semibold text-[var(--text-primary)]">
                  零件 #{idx + 1}
                </span>
                {items.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeItem(idx)}
                    disabled={pending}
                    className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--error)] disabled:opacity-50"
                  >
                    移除
                  </button>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-[var(--text-secondary)]">品牌 *</label>
                  <input
                    type="text"
                    value={it.brand}
                    onChange={(e) => updateItem(idx, "brand", e.target.value.slice(0, 40))}
                    disabled={pending}
                    placeholder="品牌"
                    className="rounded-md border border-[var(--border)] px-2 py-[6px] text-[13px] focus:border-[#10B981] focus:outline-none disabled:opacity-50"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-[var(--text-secondary)]">型號 *</label>
                  <input
                    type="text"
                    value={it.model}
                    onChange={(e) => updateItem(idx, "model", e.target.value.slice(0, 80))}
                    disabled={pending}
                    placeholder="型號"
                    className="rounded-md border border-[var(--border)] px-2 py-[6px] text-[13px] focus:border-[#10B981] focus:outline-none disabled:opacity-50"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-[var(--text-secondary)]">數量 *</label>
                  <input
                    type="number"
                    min={1}
                    max={999}
                    value={it.quantity}
                    onChange={(e) => updateItem(idx, "quantity", Math.max(1, parseInt(e.target.value, 10) || 1))}
                    disabled={pending}
                    className="rounded-md border border-[var(--border)] px-2 py-[6px] text-[13px] focus:border-[#10B981] focus:outline-none disabled:opacity-50"
                  />
                </div>
              </div>
            </div>
          ))}
          {items.length < 20 && (
            <button
              type="button"
              onClick={addItem}
              disabled={pending}
              className="rounded-md border border-dashed border-[var(--border)] bg-white px-3 py-2 text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              + 新增零件（{items.length}/20）
            </button>
          )}
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">緊急程度</label>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as MaterialUrgency)}
              disabled={pending}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#10B981] focus:outline-none disabled:opacity-50"
            >
              {urgencyOptions.map((u) => (
                <option key={u} value={u}>
                  {urgencyLabel[u]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">備註</label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 500))}
              rows={3}
              maxLength={500}
              placeholder="其他說明（選填）"
              disabled={pending}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#10B981] focus:outline-none disabled:opacity-50"
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!valid}
            className="rounded-md bg-[#065F46] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中..." : "送出缺料申請"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Reschedule Modal ─────────────────────────────── */

type RescheduleSlotInput = { start: string; end: string };

function isoToLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localInputToIso(local: string): string {
  if (!local) return "";
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString();
}

function RescheduleModal({
  pending,
  currentScheduled,
  onCancel,
  onSubmit,
}: {
  pending: boolean;
  currentScheduled: string | null;
  onCancel: () => void;
  onSubmit: (
    slots: RescheduleSlotInput[],
    message: string,
    sendVia: "line" | "line_and_sms",
  ) => Promise<void>;
}) {
  const t = useTranslations("pages.workOrderDetail.rescheduleDialog");
  const baseStart = isoToLocalInput(currentScheduled);
  const [slots, setSlots] = useState<Array<{ start: string; end: string }>>([
    { start: baseStart, end: "" },
  ]);
  const [message, setMessage] = useState("");
  const [sendVia, setSendVia] = useState<"line" | "line_and_sms">("line");

  const addSlot = () => {
    if (slots.length >= 3) return;
    setSlots([...slots, { start: "", end: "" }]);
  };
  const removeSlot = (idx: number) => {
    if (slots.length <= 1) return;
    setSlots(slots.filter((_, i) => i !== idx));
  };
  const updateSlot = (idx: number, field: "start" | "end", v: string) => {
    setSlots(slots.map((s, i) => (i === idx ? { ...s, [field]: v } : s)));
  };

  const trimmedMessage = message.trim();
  const slotsValid = slots.every((s) => {
    if (!s.start || !s.end) return false;
    const a = new Date(s.start).getTime();
    const b = new Date(s.end).getTime();
    return Number.isFinite(a) && Number.isFinite(b) && b > a;
  });
  const valid =
    slotsValid &&
    trimmedMessage.length > 0 &&
    trimmedMessage.length <= 120 &&
    !pending;

  const handleSubmit = () => {
    const isoSlots = slots.map((s) => ({
      start: localInputToIso(s.start),
      end: localInputToIso(s.end),
    }));
    onSubmit(isoSlots, trimmedMessage, sendVia);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[560px] rounded-xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <CalendarClock className="h-5 w-5 text-[#0369A1]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {t("title")}
          </span>
        </div>

        <div className="flex flex-col gap-3">
          {slots.map((s, idx) => (
            <div
              key={idx}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-page)] p-3"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[12px] font-semibold text-[var(--text-primary)]">
                  {t("slotTitle", { n: idx + 1 })}
                </span>
                {slots.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSlot(idx)}
                    disabled={pending}
                    className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--error)] disabled:opacity-50"
                  >
                    {t("removeSlot")}
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-[var(--text-secondary)]">
                    {t("startTime")}
                  </label>
                  <input
                    type="datetime-local"
                    value={s.start}
                    onChange={(e) => updateSlot(idx, "start", e.target.value)}
                    disabled={pending}
                    className="rounded-md border border-[var(--border)] bg-white px-2 py-[6px] text-[13px] focus:border-[#0EA5E9] focus:outline-none disabled:opacity-50"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-[var(--text-secondary)]">
                    {t("endTime")}
                  </label>
                  <input
                    type="datetime-local"
                    value={s.end}
                    onChange={(e) => updateSlot(idx, "end", e.target.value)}
                    disabled={pending}
                    className="rounded-md border border-[var(--border)] bg-white px-2 py-[6px] text-[13px] focus:border-[#0EA5E9] focus:outline-none disabled:opacity-50"
                  />
                </div>
              </div>
            </div>
          ))}

          {slots.length < 3 && (
            <button
              type="button"
              onClick={addSlot}
              disabled={pending}
              className="rounded-md border border-dashed border-[var(--border)] bg-white px-3 py-2 text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
            >
              {t("addSlot", { current: slots.length })}
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            {t("messageLabel")}
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, 120))}
            rows={3}
            placeholder={t("messagePlaceholder")}
            disabled={pending}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#0EA5E9] focus:outline-none disabled:opacity-50"
          />
          <span className="text-[11px] text-[var(--text-disabled)]">
            {t("messageCounter", { current: trimmedMessage.length })}
          </span>
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            {t("channelLabel")}
          </label>
          <select
            value={sendVia}
            onChange={(e) =>
              setSendVia(e.target.value as "line" | "line_and_sms")
            }
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-2 py-[6px] text-[13px] focus:border-[#0EA5E9] focus:outline-none disabled:opacity-50"
          >
            <option value="line">{t("channelLine")}</option>
            <option value="line_and_sms">{t("channelLineSms")}</option>
          </select>
        </div>

        <p className="mt-3 rounded-md bg-[#F0F9FF] px-3 py-2 text-[12px] leading-[1.6] text-[#0C4A6E]">
          {t("warning")}
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            {t("back")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!valid}
            className="rounded-md bg-[#0EA5E9] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? t("submitting") : t("submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
