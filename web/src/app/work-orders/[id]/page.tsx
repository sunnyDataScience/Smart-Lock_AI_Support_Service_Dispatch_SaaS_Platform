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
  CircleCheck,
  CircleX,
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
import WorkOrderDetailSidebar from "@/components/work-orders/WorkOrderDetailSidebar";
import MediaGallery from "@/components/work-orders/MediaGallery";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
  URGENCY_STYLE,
} from "@/components/work-orders/WorkOrdersTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];
type WorkOrderAssignRequest = components["schemas"]["WorkOrderAssignRequest"];
type AssignReasonCode = WorkOrderAssignRequest["reason_code"];
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

const ESCALATE_LEVEL_OPTIONS: { value: EscalateLevel; label: string; hint: string }[] = [
  {
    value: "operations_manager",
    label: "升級至營運主管",
    hint: "技師回報無法處理 / SLA 即將逾時 / 客訴需要更高層介入時。",
  },
  {
    value: "tenant_admin",
    label: "升級至租戶管理員",
    hint: "金額爭議 / 流程例外 / 跨部門協調，需要租戶最高權限拍板。",
  },
];

const ASSIGN_REASON_OPTIONS: { value: AssignReasonCode; label: string }[] = [
  { value: "auto_dispatch_exhausted", label: "自動派工已耗盡候選" },
  { value: "customer_requested_specific_tech", label: "客戶指定技師" },
  { value: "skill_shortage_override", label: "技能不足但人手吃緊" },
  { value: "sla_rescue", label: "SLA 救援" },
  { value: "other", label: "其他" },
];

const PC_STATUS_STYLE: Record<
  ProblemCardStatus,
  { label: string; color: string; bg: string }
> = {
  draft: { label: "草稿", color: "#6366F1", bg: "#EEF2FF" },
  confirmed: { label: "已確認", color: "#3B82F6", bg: "#DBEAFE" },
  resolved: { label: "已解決", color: "#10B981", bg: "#D1FAE5" },
};

/* ── SLA Timeline (mock) ─────────────────────────── */

const slaNodes = [
  { label: "建立", time: "09:00", done: true },
  { label: "派工", time: "09:15", done: true },
  { label: "接受", time: "09:32", done: true },
  { label: "進行中", time: "10:45", active: true },
  { label: "完工" },
  { label: "確認" },
];

function SlaTimeline() {
  return (
    <div className="flex flex-col gap-2 rounded-lg bg-[var(--bg-page)] p-3">
      <div className="flex items-center justify-between">
        {slaNodes.map((n) => (
          <div key={n.label} className="flex flex-col items-center gap-1">
            {n.active ? (
              <div className="h-4 w-4 rounded-full border-[3px] border-[var(--primary)] bg-white" />
            ) : n.done ? (
              <div className="h-3 w-3 rounded-full bg-[var(--success)]" />
            ) : (
              <div className="h-3 w-3 rounded-full border-[1.5px] border-[#CBD5E1] bg-white" />
            )}
            <span
              className={`text-[11px] ${n.active ? "font-semibold text-[var(--primary)]" : "text-[var(--text-secondary)]"}`}
            >
              {n.label}
            </span>
            {n.time && (
              <span className="text-[10px] text-[var(--text-disabled)]">
                {n.time}
              </span>
            )}
          </div>
        ))}
        <span className="text-[14px] font-semibold text-[var(--warning)]">
          剩餘 02:15
        </span>
      </div>
      <div className="h-2 w-full rounded bg-[var(--border)]">
        <div className="h-2 w-[60%] rounded bg-[var(--primary)]" />
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
          `/api/v1/problem-cards/${encodeURIComponent(pcId)}`,
        );
        if (cancelled) return;
        const data = res.data ?? null;
        setCard(data);
        onLoaded?.(data);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pcId, onLoaded]);

  const pcStatus = card ? PC_STATUS_STYLE[card.status] : null;
  const pcUrgency = card ? URGENCY_STYLE[card.urgency] : null;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center gap-3">
        <FileText className="h-5 w-5 text-[var(--primary)]" />
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          問題診斷摘要
        </span>
        <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[12px] text-[var(--primary)]">
          ProblemCard
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
          此工單未關聯問題卡
        </span>
      )}
      {error && (
        <span className="text-[13px] text-red-600">載入失敗：{error}</span>
      )}
      {loading && !card && (
        <span className="text-[13px] text-[var(--text-disabled)]">
          載入問題卡中…
        </span>
      )}

      {card && (
        <>
          <div className="flex items-center gap-2">
            {pcStatus && (
              <span
                className="rounded-full px-3 py-1 text-[12px] font-semibold"
                style={{ color: pcStatus.color, backgroundColor: pcStatus.bg }}
              >
                {pcStatus.label}
              </span>
            )}
            {pcUrgency && (
              <span
                className="rounded px-2 py-1 text-[11px] font-medium"
                style={{ color: pcUrgency.color, backgroundColor: pcUrgency.bg }}
              >
                緊急度 {pcUrgency.label}
              </span>
            )}
            {card.confidence_score != null && (
              <span className="text-[12px] text-[var(--text-secondary)]">
                AI 信心 {(card.confidence_score * 100).toFixed(0)}%
              </span>
            )}
          </div>

          <div className="grid grid-cols-4 gap-2">
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                品牌
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {card.brand || "—"}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                型號
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {card.model || "—"}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                類別
              </span>
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {card.category || "—"}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-lg bg-[#F1F5F9] p-3">
              <span className="text-[11px] text-[var(--text-secondary)]">
                關聯對話
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
              症狀描述
            </span>
            <p className="mt-1 text-[13px] leading-[1.6] text-[var(--text-primary)]">
              {card.symptom || "—"}
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
          `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
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
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
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
            客戶上傳媒體
          </span>
          <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[11px] font-semibold text-[var(--primary)]">
            LINE
          </span>
          {items.length > 0 && (
            <span className="text-[12px] text-[var(--text-secondary)]">
              共 {items.length} 則
            </span>
          )}
        </div>
      </div>

      {!conversationId && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          此工單未關聯對話，無媒體可顯示
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          載入媒體失敗：{error}
        </div>
      )}

      {conversationId && loading && items.length === 0 && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          載入媒體中…
        </div>
      )}

      {conversationId && !loading && items.length === 0 && !error && (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          客戶尚未上傳任何媒體
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
              title={`提交時間：${formatDateTime(m.created_at)}`}
            >
              <div className="relative h-[128px] w-[128px] overflow-hidden rounded-lg border border-[var(--border)] bg-[#F1F5F9]">
                {m.type === "image" ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={m.media_url ?? ""}
                    alt="客戶上傳"
                    className="h-full w-full object-cover transition-transform group-hover:scale-[1.03]"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[12px] text-[var(--text-secondary)]">
                    🎬 影片
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

interface TimelineEvent {
  color: string;
  badge: { text: string; textColor: string; bg: string };
  title: string;
  detail?: string;
  time: string | null | undefined;
}

const SYS_BADGE = { text: "系統", textColor: "#64748B", bg: "#F1F5F9" };
const TECH_BADGE = { text: "技師", textColor: "#1E40AF", bg: "#DBEAFE" };
const SCHED_BADGE = { text: "排程", textColor: "#9F1239", bg: "#FFE4E6" };
const COMPLETE_BADGE = { text: "完工", textColor: "#065F46", bg: "#D1FAE5" };

function buildEvents(order: WorkOrder | null): TimelineEvent[] {
  if (!order) return [];
  const list: TimelineEvent[] = [];

  list.push({
    color: "#94A3B8",
    badge: SYS_BADGE,
    title: "工單建立",
    detail: order.problem_card_id
      ? `由問題卡 ${order.problem_card_id.slice(0, 8)} 衍生`
      : undefined,
    time: order.created_at,
  });

  if (order.scheduled_time) {
    list.push({
      color: "#F43F5E",
      badge: SCHED_BADGE,
      title: "預計到場時間",
      detail: order.technician_id
        ? `技師 ${order.technician_id.slice(0, 8)} 已排程`
        : "尚未指派技師",
      time: order.scheduled_time,
    });
  }

  if (order.actual_arrival) {
    list.push({
      color: "#3B82F6",
      badge: TECH_BADGE,
      title: "技師抵達現場",
      time: order.actual_arrival,
    });
  }

  if (order.completion_time) {
    list.push({
      color: "#10B981",
      badge: COMPLETE_BADGE,
      title: "工單完工",
      time: order.completion_time,
    });
  }

  if (order.updated_at && order.updated_at !== order.created_at) {
    list.push({
      color: "#94A3B8",
      badge: SYS_BADGE,
      title: "最後更新",
      detail: `目前狀態：${order.status}`,
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
  const events = buildEvents(order);
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          工單歷程
        </span>
        <button
          disabled
          title="即將推出"
          className="flex items-center gap-[6px] rounded-md border border-[var(--border)] px-3 py-[6px] opacity-60"
        >
          <span className="text-[13px] text-[var(--text-secondary)]">全部</span>
          <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
        </button>
      </div>

      {events.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)] px-4 py-6 text-center text-[13px] text-[var(--text-disabled)]">
          尚無歷程資料
        </div>
      ) : (
        <div className="relative">
          <div className="absolute bottom-0 left-[5px] top-[6px] w-[2px] bg-[var(--border)]" />
          <div className="flex flex-col gap-5">
            {events.map((ev, i) => (
              <div key={i} className="flex gap-4 pt-[2px]">
                <div
                  className="relative z-10 mt-[2px] h-3 w-3 flex-shrink-0 rounded-full"
                  style={{ backgroundColor: ev.color }}
                />
                <div className="flex flex-col gap-1">
                  <span
                    className="inline-flex w-fit rounded px-2 py-[2px] text-[11px]"
                    style={{ color: ev.badge.textColor, backgroundColor: ev.badge.bg }}
                  >
                    {ev.badge.text}
                  </span>
                  <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                    {ev.title}
                  </span>
                  {ev.detail && (
                    <span className="text-[12px] text-[var(--text-secondary)]">
                      {ev.detail}
                    </span>
                  )}
                  <span className="text-[11px] text-[var(--text-disabled)]">
                    {formatDateTime(ev.time)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Conversation Thread (mock) ──────────────────── */

function ConversationThread() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          LINE 對話記錄（示意）
        </span>
        <div className="flex items-center gap-[6px] opacity-60">
          <span className="text-[13px] text-[var(--primary)]">在新視窗開啟</span>
          <ExternalLink className="h-[14px] w-[14px] text-[var(--primary)]" />
        </div>
      </div>
      <div className="flex max-h-[160px] items-center justify-center rounded-lg bg-[var(--bg-page)] p-4">
        <span className="text-[13px] text-[var(--text-disabled)]">
          示意：問題卡關聯對話將顯示於此
        </span>
      </div>
      <div className="flex items-center justify-center gap-[6px] rounded-b-lg bg-[#F1F5F9] px-4 py-2">
        <Lock className="h-3 w-3 text-[var(--text-disabled)]" />
        <span className="text-[12px] text-[var(--text-disabled)]">
          唯讀模式 — 此為 LINE 對話備份
        </span>
      </div>
    </div>
  );
}

/* ── Completion Report (mock) ────────────────────── */

const funcTests = [
  { label: "指紋解鎖", pass: true },
  { label: "密碼解鎖", pass: true },
  { label: "電池電壓 (示意)", pass: false },
];

function CompletionReport() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-[var(--success)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            完工報告（示意）
          </span>
        </div>
        <span className="text-[12px] text-[var(--text-secondary)]">
          提交時間：—
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
          功能測試
        </span>
        <div className="flex flex-col gap-[6px]">
          {funcTests.map((t) => (
            <div key={t.label} className="flex items-center gap-2">
              {t.pass ? (
                <CircleCheck className="h-[18px] w-[18px] text-[var(--success)]" />
              ) : (
                <CircleX className="h-[18px] w-[18px] text-[var(--error)]" />
              )}
              <span className="text-[13px] text-[var(--text-primary)]">
                {t.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Exception Records (mock) ────────────────────── */

function ExceptionRecords() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TriangleAlert className="h-5 w-5 text-[var(--error)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            異常記錄（示意）
          </span>
        </div>
      </div>
      <div className="flex h-16 items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--bg-page)]">
        <span className="text-[13px] text-[var(--text-disabled)]">
          示意：工單異常事件將顯示於此
        </span>
      </div>
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
  | null;

export default function WorkOrderDetailPage({ params }: PageProps) {
  const { id } = use(params);
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
        const res = await api.get<WorkOrderEnvelope>(
          `/api/v1/work-orders/${encodeURIComponent(id)}`,
        );
        if (!cancelled) setOrder(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
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
    e instanceof ApiError
      ? `${e.errorCode} (${e.status})：${e.message}`
      : e instanceof Error
        ? e.message
        : String(e);

  const handleAccept = async () => {
    setActionPending("accept");
    setActionError(null);
    try {
      const res = await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(id)}/accept`,
      );
      setOrder(res.data ?? null);
      setActionToast("已接受派工");
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
        `/api/v1/work-orders/${encodeURIComponent(id)}/complete`,
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast("工單已標記完工");
    } catch (e) {
      setActionError(formatActionError(e));
    } finally {
      setActionPending(null);
    }
  };

  const handleCancel = async (reason: string) => {
    setActionPending("cancel");
    setActionError(null);
    try {
      const res = await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(id)}/cancel`,
        reason ? { reason } : {},
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast("工單已取消");
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
      const body: Record<string, unknown> = {
        technician_id: technicianId,
        reason_code: reasonCode,
      };
      if (reasonText) body.reason_text = reasonText;
      const res = await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(id)}/assign`,
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast("已指派技師");
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
        `/api/v1/work-orders/${encodeURIComponent(id)}/confirm`,
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast("客戶已確認結案");
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
        `/api/v1/work-orders/${encodeURIComponent(id)}/signature`,
        body,
      );
      setActionMode(null);
      setActionToast(res.message || "雙方簽章完成");
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
        `/api/v1/work-orders/${encodeURIComponent(id)}/escalate`,
        body,
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      const tone =
        level === "operations_manager" ? "已升級至營運主管" : "已升級至租戶管理員";
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
      const res = await api.post<WorkOrderEnvelope>(
        `/api/v1/work-orders/${encodeURIComponent(id)}/reschedule`,
        {
          proposed_slots: slots,
          message_to_customer: message,
          send_via: sendVia,
        },
      );
      setOrder(res.data ?? null);
      setActionMode(null);
      setActionToast(`改期請求已送出（${slots.length} 個備選時段）`);
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
  const statusGroup = order ? STATUS_GROUP_MAP[order.status] : null;
  const statusStyle = statusGroup ? STATUS_GROUP_STYLE[statusGroup] : null;
  const urgencyStyle = order ? URGENCY_STYLE[order.urgency] : null;
  const districtAddr = order
    ? order.district && !order.address.startsWith(order.district)
      ? `${order.district} · ${order.address}`
      : order.address || "—"
    : "—";

  const canAccept = order ? ACCEPT_FROM.has(order.status) : false;
  const canAssign = order ? ASSIGN_FROM.has(order.status) : false;
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
  const assignLabel = order?.technician_id ? "重新指派" : "指派技師";

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-auto">
          {/* Detail Header */}
          <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
            <span className="text-[11px] text-[var(--text-secondary)]">
              首頁 &gt; 工單管理 &gt; 工單列表 &gt; {shortId}
            </span>
            <div className="flex items-center gap-3">
              <Link
                href="/work-orders"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--bg-page)]"
              >
                <ChevronLeft className="h-5 w-5 text-[var(--text-secondary)]" />
              </Link>
              <span className="font-mono text-[28px] font-bold text-[var(--text-primary)]" title={id}>
                {shortId}
              </span>
              {statusStyle && (
                <span
                  className="rounded px-2 py-1 text-[14px] font-semibold"
                  style={{ color: statusStyle.color, backgroundColor: statusStyle.bg }}
                >
                  {statusStyle.label}
                </span>
              )}
              {urgencyStyle && (
                <span
                  className="rounded px-2 py-1 text-[12px] font-medium"
                  style={{ color: urgencyStyle.color, backgroundColor: urgencyStyle.bg }}
                >
                  緊急度：{urgencyStyle.label}
                </span>
              )}
              <Copy className="h-4 w-4 text-[var(--text-secondary)]" />
            </div>
            {order && (
              <div className="flex flex-wrap items-center gap-4 text-[13px] text-[var(--text-secondary)]">
                <span>
                  品牌：
                  <span className="font-medium text-[var(--text-primary)]">{order.brand || "—"}</span>
                </span>
                <span>
                  型號：
                  <span className="font-medium text-[var(--text-primary)]">{order.model || "—"}</span>
                </span>
                <span>
                  地址：
                  <span className="font-medium text-[var(--text-primary)]">{districtAddr}</span>
                </span>
                {order.problem_card_id && (
                  <Link
                    href={`/problem-cards/${order.problem_card_id}`}
                    className="font-mono text-[var(--primary)] hover:underline"
                  >
                    關聯問題卡：{order.problem_card_id.slice(0, 8)}
                  </Link>
                )}
              </div>
            )}
            <SlaTimeline />

            {anyAction && (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {canAccept && (
                  <button
                    onClick={handleAccept}
                    disabled={actionPending !== null}
                    className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    {actionPending === "accept" ? "處理中…" : "接受派工"}
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
                    標記完工
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
                    取消工單
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
                    確認結案
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
                    升級工單
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
                    電子簽章
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
                    送出改期
                  </button>
                )}
              </div>
            )}

            {actionError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                操作失敗：{actionError}
              </div>
            )}
          </div>

          {error && (
            <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入工單失敗：{error}
            </div>
          )}

          {loading && !order && (
            <div className="mx-8 mt-4 text-[13px] text-[var(--text-secondary)]">
              載入中…
            </div>
          )}

          <div className="mx-8 my-4 flex items-start gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3">
            <Info className="mt-[2px] h-4 w-4 flex-shrink-0 text-[#64748B]" />
            <span className="text-[13px] leading-[1.6] text-[#475569]">
              問題診斷摘要、客戶上傳媒體、工單歷程為即時資料；SLA 時間軸、對話內容、完工報告與異常為示意，待 SLA / 完工報告模組接入後將顯示真實資料。
            </span>
          </div>

          <ProblemCardSummary
            pcId={order?.problem_card_id}
            onLoaded={setProblemCard}
          />
          <LineMediaGallery conversationId={problemCard?.conversation_id} />
          <MediaGallery workOrderId={id} />
          <WorkTimeline order={order} />
          <ConversationThread />
          <CompletionReport />
          <ExceptionRecords />
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
            標記完工
          </span>
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              完工摘要 <span className="text-[var(--error)]">*</span>
            </label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="例如：更換主板、測試指紋與密碼解鎖正常"
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {trimmed.length} / 2000
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              實收金額（NT$，可留空）
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={actualAmount}
              onChange={(e) => setActualAmount(e.target.value)}
              placeholder="例如：3500.00"
              className={`rounded-md border px-3 py-2 text-[13px] focus:outline-none ${
                amountValid
                  ? "border-[var(--border)] focus:border-[var(--primary)]"
                  : "border-red-300 focus:border-red-400"
              }`}
            />
            {!amountValid && (
              <span className="text-[11px] text-red-600">
                金額格式應為小數兩位內的數字
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
            取消
          </button>
          <button
            onClick={() => onSubmit(trimmed, actualAmount.trim() || null)}
            disabled={!canSubmit}
            className="rounded-md bg-[var(--success)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認完工"}
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
          "/api/v1/dispatch/candidates",
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
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
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
    if (km == null) return "—";
    if (km === 0) return "區內";
    return `≈ ${km} km`;
  };
  const formatEta = (min: number | null | undefined): string =>
    min == null ? "—" : `${min} 分鐘可達`;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[640px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            {currentTechnicianId ? "重新指派技師" : "指派技師"}
          </span>
          <span className="ml-auto text-[11px] text-[var(--text-disabled)]">
            綜合分 = 0.4 技能 + 0.3 距離 + 0.3 評分
          </span>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              候選技師（依綜合分排序） <span className="text-[var(--error)]">*</span>
            </label>
            {techsLoading ? (
              <div className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] text-[var(--text-disabled)]">
                計算候選技師中…
              </div>
            ) : techsError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                載入失敗：{techsError}
              </div>
            ) : candidates.length === 0 ? (
              <div className="rounded-md border border-dashed border-[var(--border)] px-3 py-2 text-[13px] text-[var(--text-disabled)]">
                目前無可派候選技師（已排除歇業 / 熔斷狀態）
              </div>
            ) : (
              <div className="flex max-h-[320px] flex-col gap-2 overflow-y-auto pr-1">
                {candidates.map((c) => {
                  const t = c.technician;
                  const active = selected === t.id;
                  const isCurrent = t.id === currentTechnicianId;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setSelected(t.id)}
                      className={`flex flex-col gap-1 rounded-lg border px-3 py-2 text-left transition ${
                        active
                          ? "border-[var(--primary)] bg-[var(--primary-light)]"
                          : "border-[var(--border)] bg-white hover:bg-[var(--bg-page)]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                          {t.name}
                        </span>
                        <span className="text-[11px] text-[var(--text-secondary)]">
                          {t.phone}
                        </span>
                        {isCurrent && (
                          <span className="rounded bg-[#FEF3C7] px-2 py-[1px] text-[10px] font-medium text-[#92400E]">
                            目前已指派
                          </span>
                        )}
                        <span
                          className="ml-auto rounded px-2 py-[2px] text-[12px] font-bold text-white"
                          style={{ backgroundColor: scoreColor(c.score) }}
                          title="綜合分（0~100）"
                        >
                          {c.score.toFixed(1)}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--text-secondary)]">
                        <span>
                          技能 {((c.skill_match ?? 0) * 100).toFixed(0)}%
                        </span>
                        <span>距離 {formatDistance(c.distance_km)}</span>
                        <span>評分 {t.rating.toFixed(1)} / 5</span>
                        <span>{formatEta(c.availability_eta_minutes)}</span>
                        {t.skills.length > 0 && (
                          <span title={t.skills.join(", ")}>
                            專長 {t.skills.slice(0, 2).join("、")}
                            {t.skills.length > 2 ? "…" : ""}
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
              指派原因 <span className="text-[var(--error)]">*</span>
            </label>
            <select
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value as AssignReasonCode)}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            >
              {ASSIGN_REASON_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              補充說明（可留空）
            </label>
            <textarea
              value={reasonText}
              onChange={(e) => setReasonText(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="例如：客戶指名張師傅、附近僅此技師具備該品牌維修經驗"
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {reasonText.trim().length} / 500
            </span>
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
            onClick={() => onSubmit(selected, reasonCode, reasonText.trim())}
            disabled={!canSubmit}
            className="rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認指派"}
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
  onSubmit: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-[480px] rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-2">
          <X className="h-5 w-5 text-[var(--error)]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            取消工單
          </span>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            取消原因（可留空）
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            maxLength={500}
            placeholder="例如：客戶改約、重複建立工單"
            className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[var(--primary)] focus:outline-none"
          />
          <span className="text-[11px] text-[var(--text-disabled)]">
            {trimmed.length} / 500
          </span>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            返回
          </button>
          <button
            onClick={() => onSubmit(trimmed)}
            disabled={pending}
            className="rounded-md bg-[var(--error)] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認取消"}
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
  const [rating, setRating] = useState<number>(5);
  const [hover, setHover] = useState<number>(0);
  const [feedback, setFeedback] = useState("");
  const trimmed = feedback.trim();
  const valid = rating >= 1 && rating <= 5 && trimmed.length <= 1000;
  const display = hover > 0 ? hover : rating;
  const ratingHints: Record<number, string> = {
    1: "極不滿意",
    2: "不滿意",
    3: "普通",
    4: "滿意",
    5: "非常滿意",
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
          <Star className="h-5 w-5 text-[#0EA5E9]" />
          <span className="text-[18px] font-semibold text-[var(--text-primary)]">
            客戶確認結案
          </span>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              滿意度評分 <span className="text-[var(--error)]">*</span>
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
                    aria-label={`給 ${n} 星`}
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
                {ratingHints[display] ?? ""}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--text-secondary)]">
              客戶意見（可留空，最多 1000 字）
            </label>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value.slice(0, 1000))}
              rows={4}
              placeholder="例如：技師準時到場、解說清楚，鎖具運作正常"
              className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#0EA5E9] focus:outline-none"
            />
            <span className="text-[11px] text-[var(--text-disabled)]">
              {trimmed.length} / 1000
            </span>
          </div>
        </div>

        <p className="mt-3 rounded-md bg-[#E0F2FE] px-3 py-2 text-[12px] leading-[1.6] text-[#075985]">
          確認結案為終局狀態 — 一旦送出無法再切回 in_progress / completed。
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            返回
          </button>
          <button
            onClick={() => onSubmit(rating, trimmed)}
            disabled={pending || !valid}
            className="rounded-md bg-[#0EA5E9] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認結案"}
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
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    if (!file.type.startsWith("image/")) {
      setError("請選擇圖片檔（PNG / JPEG / SVG）");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("檔案過大，請小於 2 MB");
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
    reader.onerror = () => setError("檔案讀取失敗");
    reader.readAsDataURL(file);
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-3">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">{label}</span>
      {value ? (
        <div className="flex items-center gap-3">
          <div className="flex h-[64px] w-[64px] items-center justify-center rounded border border-[var(--border)] bg-white text-[10px] text-[var(--text-disabled)]">
            base64
          </div>
          <div className="flex flex-col">
            <span className="text-[12px] font-medium text-[var(--text-primary)]">
              已上傳（{value.length.toLocaleString()} 字元）
            </span>
            <button
              type="button"
              onClick={() => onChange(null)}
              className="mt-1 self-start text-[11px] text-[var(--error)] hover:underline"
            >
              清除重傳
            </button>
          </div>
        </div>
      ) : (
        <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-[var(--border)] bg-white px-3 py-2 text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-page)]">
          <Upload className="h-4 w-4" />
          選擇簽章圖片（PNG / JPEG / SVG，{"<"}2 MB）
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
  const [customer, setCustomer] = useState<string | null>(null);
  const [technician, setTechnician] = useState<string | null>(null);
  const [gpsLat, setGpsLat] = useState<string>("");
  const [gpsLng, setGpsLng] = useState<string>("");
  const [gpsError, setGpsError] = useState<string | null>(null);

  const valid = !!customer && !!technician;

  const captureGps = () => {
    if (!navigator.geolocation) {
      setGpsError("此裝置不支援定位");
      return;
    }
    setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsLat(pos.coords.latitude.toFixed(6));
        setGpsLng(pos.coords.longitude.toFixed(6));
      },
      (err) => setGpsError(err.message || "定位失敗"),
      { timeout: 8000 },
    );
  };

  const submit = () => {
    if (!customer || !technician) return;
    const lat = gpsLat.trim() ? Number(gpsLat) : null;
    const lng = gpsLng.trim() ? Number(gpsLng) : null;
    if ((lat != null && Number.isNaN(lat)) || (lng != null && Number.isNaN(lng))) {
      setGpsError("經緯度需為數字");
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
            雙方電子簽章
          </span>
        </div>

        <p className="mb-3 rounded-md bg-[#F5F3FF] px-3 py-2 text-[12px] leading-[1.6] text-[#5B21B6]">
          客戶與技師雙方簽章將寫入 digital_signatures，並以 SHA-256 產生整合性雜湊。
          已簽章的角色不會被覆寫；雙方均完成後此工單無法再次簽章。
        </p>

        <div className="flex flex-col gap-3">
          <SignaturePadField
            label="客戶簽章 *"
            value={customer}
            onChange={setCustomer}
          />
          <SignaturePadField
            label="技師簽章 *"
            value={technician}
            onChange={setTechnician}
          />

          <div className="rounded-lg border border-[var(--border)] bg-[#F8FAFC] p-3">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                GPS 位置（可選，作為簽章地點佐證）
              </span>
              <button
                type="button"
                onClick={captureGps}
                disabled={pending}
                className="rounded-md border border-[var(--border)] bg-white px-2 py-1 text-[11px] font-medium text-[var(--primary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                取得目前位置
              </button>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input
                type="text"
                value={gpsLat}
                onChange={(e) => setGpsLat(e.target.value)}
                placeholder="緯度（lat）"
                className="rounded-md border border-[var(--border)] px-3 py-2 text-[12px] focus:border-[#7C3AED] focus:outline-none"
              />
              <input
                type="text"
                value={gpsLng}
                onChange={(e) => setGpsLng(e.target.value)}
                placeholder="經度（lng）"
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
            返回
          </button>
          <button
            onClick={submit}
            disabled={pending || !valid}
            className="rounded-md bg-[#7C3AED] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認簽章"}
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
  const [level, setLevel] = useState<EscalateLevel>("operations_manager");
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 500;
  const activeOption = ESCALATE_LEVEL_OPTIONS.find((o) => o.value === level);

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
            升級工單
          </span>
        </div>

        <div className="flex flex-col gap-2">
          {ESCALATE_LEVEL_OPTIONS.map((opt) => {
            const active = opt.value === level;
            return (
              <button
                key={opt.value}
                onClick={() => setLevel(opt.value)}
                className={`rounded-lg border px-3 py-3 text-left transition ${
                  active
                    ? "border-[#B45309] bg-[#FEF3C7]"
                    : "border-[var(--border)] hover:bg-[var(--bg-page)]"
                }`}
              >
                <div className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {opt.label}
                </div>
                <div className="mt-1 text-[12px] leading-[1.5] text-[var(--text-secondary)]">
                  {opt.hint}
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            升級原因（必填，最多 500 字）
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 500))}
            rows={4}
            placeholder={
              activeOption
                ? `說明為何需要 ${activeOption.label}（將寫入 service_report 稽核軌跡）`
                : "請填寫升級原因"
            }
            className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#B45309] focus:outline-none"
          />
          <span className="text-[11px] text-[var(--text-disabled)]">
            {trimmed.length} / 500
          </span>
        </div>

        <p className="mt-3 rounded-md bg-[#FEF3C7] px-3 py-2 text-[12px] leading-[1.6] text-[#92400E]">
          升級後 priority 會推進到 urgent，工單仍維持當前狀態以等候上層覆審。
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            返回
          </button>
          <button
            onClick={() => onSubmit(level, trimmed)}
            disabled={pending || !valid}
            className="rounded-md bg-[#B45309] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "確認升級"}
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
            送出改期請求
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
                  備選時段 {idx + 1}
                </span>
                {slots.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSlot(idx)}
                    disabled={pending}
                    className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--error)] disabled:opacity-50"
                  >
                    移除
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-[var(--text-secondary)]">
                    開始時間
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
                    結束時間
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
              + 新增備選時段（{slots.length}/3）
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            告知客戶訊息（必填，最多 120 字）
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, 120))}
            rows={3}
            placeholder="技師臨時被叫去處理鄰居緊急事件，請選一個方便的備選時段"
            disabled={pending}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-[13px] focus:border-[#0EA5E9] focus:outline-none disabled:opacity-50"
          />
          <span className="text-[11px] text-[var(--text-disabled)]">
            {trimmedMessage.length} / 120
          </span>
        </div>

        <div className="mt-4 flex flex-col gap-1">
          <label className="text-[12px] font-medium text-[var(--text-secondary)]">
            通知管道
          </label>
          <select
            value={sendVia}
            onChange={(e) =>
              setSendVia(e.target.value as "line" | "line_and_sms")
            }
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-2 py-[6px] text-[13px] focus:border-[#0EA5E9] focus:outline-none disabled:opacity-50"
          >
            <option value="line">LINE</option>
            <option value="line_and_sms">LINE + SMS</option>
          </select>
        </div>

        <p className="mt-3 rounded-md bg-[#F0F9FF] px-3 py-2 text-[12px] leading-[1.6] text-[#0C4A6E]">
          MVP 版本不會真的推播 LINE/SMS，但首選時段會立即更新到 scheduled_at；
          24 小時內最多可改期 3 次，超過將回 RESCHEDULE_LIMIT_EXCEEDED。
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-[var(--border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-page)] disabled:opacity-50"
          >
            返回
          </button>
          <button
            onClick={handleSubmit}
            disabled={!valid}
            className="rounded-md bg-[#0EA5E9] px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送出中…" : "送出改期"}
          </button>
        </div>
      </div>
    </div>
  );
}
