"use client";

import { use, useEffect, useState } from "react";
import {
  ChevronLeft,
  Copy,
  FileText,
  ChevronUp,
  ChevronDown,
  ArrowRight,
  Images,
  Package,
  ExternalLink,
  Lock,
  ClipboardCheck,
  CircleCheck,
  CircleX,
  TriangleAlert,
  Info,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import WorkOrderDetailSidebar from "@/components/work-orders/WorkOrderDetailSidebar";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
  URGENCY_STYLE,
} from "@/components/work-orders/WorkOrdersTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];
type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardEnvelope = components["schemas"]["ProblemCardEnvelope"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];

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

function ProblemCardSummary({ pcId }: { pcId?: string }) {
  const [card, setCard] = useState<ProblemCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pcId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCard(null);
    (async () => {
      try {
        const res = await api.get<ProblemCardEnvelope>(
          `/api/v1/problem-cards/${encodeURIComponent(pcId)}`,
        );
        if (!cancelled) setCard(res.data ?? null);
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
  }, [pcId]);

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

/* ── LINE Media Gallery (mock) ───────────────────── */

const mediaTabs = [
  { label: "全部", active: true },
  { label: "圖片", active: false },
  { label: "影片", active: false },
  { label: "Issue 包", active: false },
];

function LineMediaGallery() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Images className="h-5 w-5 text-[var(--primary)]" />
          <span className="text-[20px] font-semibold text-[var(--text-primary)]">
            客戶上傳媒體（示意）
          </span>
          <span className="rounded bg-[var(--primary-light)] px-2 py-1 text-[11px] font-semibold text-[var(--primary)]">
            LINE
          </span>
        </div>
        <div className="flex gap-1">
          {mediaTabs.map((t) => (
            <span
              key={t.label}
              className={`rounded px-3 py-1 text-[12px] font-medium ${t.active ? "bg-[var(--primary)] text-white" : "bg-[var(--bg-page)] text-[var(--text-secondary)]"}`}
            >
              {t.label}
            </span>
          ))}
        </div>
      </div>
      <div className="flex flex-col rounded-lg border border-[var(--border)]">
        <div className="flex items-center gap-3 rounded-t-lg bg-[#F8FAFC] p-3">
          <Package className="h-5 w-5 text-[var(--primary)]" />
          <div className="flex flex-1 flex-col gap-[2px]">
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              示意：客戶於 LINE 上傳的媒體將集結於此
            </span>
            <span className="text-[11px] text-[var(--text-secondary)]">
              提交時間 —
            </span>
          </div>
          <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
        </div>
        <div className="flex flex-col gap-4 p-4">
          <div className="flex gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`h-[128px] w-[128px] flex-shrink-0 rounded-lg ${i % 2 === 0 ? "bg-[#CBD5E1]" : "bg-[#E2E8F0]"}`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Work Timeline (mock) ────────────────────────── */

interface TimelineEvent {
  color: string;
  badge: { text: string; textColor: string; bg: string };
  title: string;
  detail?: string;
  time: string;
}

const events: TimelineEvent[] = [
  {
    color: "#3B82F6",
    badge: { text: "技師", textColor: "#1E40AF", bg: "#DBEAFE" },
    title: "示意：狀態變更會記錄在此",
    detail: "派工模組接入後將顯示真實時間軸",
    time: "—",
  },
  {
    color: "#94A3B8",
    badge: { text: "系統", textColor: "#64748B", bg: "#F1F5F9" },
    title: "示意：工單自動建立",
    detail: "由 LINE 對話自動觸發",
    time: "—",
  },
];

function WorkTimeline() {
  return (
    <div className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <span className="text-[20px] font-semibold text-[var(--text-primary)]">
          工單歷程（示意）
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
                  {ev.time}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
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

export default function WorkOrderDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const shortId = id.slice(0, 8);
  const statusGroup = order ? STATUS_GROUP_MAP[order.status] : null;
  const statusStyle = statusGroup ? STATUS_GROUP_STYLE[statusGroup] : null;
  const urgencyStyle = order ? URGENCY_STYLE[order.urgency] : null;
  const districtAddr = order
    ? order.district && !order.address.startsWith(order.district)
      ? `${order.district} · ${order.address}`
      : order.address || "—"
    : "—";

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
              以下 SLA 時間軸、媒體、工單歷程、對話記錄、完工報告與異常為示意，待派工模組接入後將顯示真實資料；問題診斷摘要為即時資料。
            </span>
          </div>

          <ProblemCardSummary pcId={order?.problem_card_id} />
          <LineMediaGallery />
          <WorkTimeline />
          <ConversationThread />
          <CompletionReport />
          <ExceptionRecords />
        </div>

        <WorkOrderDetailSidebar workOrder={order ?? undefined} />
      </div>
    </div>
  );
}
