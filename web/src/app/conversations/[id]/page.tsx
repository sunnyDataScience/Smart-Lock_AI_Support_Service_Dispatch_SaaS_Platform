"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ChatTimeline from "@/components/conversations/ChatTimeline";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationEnvelope = components["schemas"]["ConversationEnvelope"];
type Message = components["schemas"]["Message"];
type MessagePage = components["schemas"]["MessagePage"];
type ConversationStatus = components["schemas"]["ConversationStatus"];
type ProblemCard = components["schemas"]["ProblemCard"];
type ProblemCardPage = components["schemas"]["ProblemCardPage"];
type ProblemCardStatus = components["schemas"]["ProblemCardStatus"];

const PC_STATUS_LABEL: Record<ProblemCardStatus, { label: string; bg: string; color: string }> = {
  draft: { label: "草稿", bg: "#EEF2FF", color: "#6366F1" },
  confirmed: { label: "已確認", bg: "#DBEAFE", color: "#3B82F6" },
  resolved: { label: "已解決", bg: "#D1FAE5", color: "#10B981" },
};

const STATUS_LABEL: Record<ConversationStatus, string> = {
  active: "進行中",
  waiting_human: "已升級",
  closed: "已結束",
};

const STATUS_COLOR: Record<ConversationStatus, { bg: string; text: string }> = {
  active: { bg: "#EFF6FF", text: "#2563EB" },
  waiting_human: { bg: "#FEF2F2", text: "#EF4444" },
  closed: { bg: "#ECFDF5", text: "#10B981" },
};

const RESOLUTION_LABEL: Record<string, string> = {
  case_library: "案例庫",
  rag: "RAG",
  human: "人工",
};

export default function ConversationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [problemCards, setProblemCards] = useState<ProblemCard[]>([]);
  const [pcLoading, setPcLoading] = useState(false);
  const [pcError, setPcError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setNotFound(false);
      setPcLoading(true);
      setPcError(null);
      setProblemCards([]);
      try {
        const [envelope, page, pcPage] = await Promise.all([
          api.get<ConversationEnvelope>(`/api/v1/conversations/${id}`),
          api.get<MessagePage>(`/api/v1/conversations/${id}/messages`, {
            query: { limit: 100 },
          }),
          api
            .get<ProblemCardPage>(`/api/v1/problem-cards`, {
              query: { conversation_id: id, limit: 10 },
            })
            .catch((e: unknown): ProblemCardPage | null => {
              if (cancelled) return null;
              setPcError(
                e instanceof ApiError
                  ? `${e.errorCode} (${e.status})`
                  : e instanceof Error
                    ? e.message
                    : String(e),
              );
              return null;
            }),
        ]);
        if (cancelled) return;
        setConv(envelope.data ?? null);
        setMessages(page.items ?? []);
        setProblemCards((pcPage?.items ?? []) as ProblemCard[]);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
        } else {
          setError(
            e instanceof ApiError
              ? `${e.errorCode} (${e.status})：${e.message}`
              : e instanceof Error
                ? e.message
                : String(e),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setPcLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-6">
          <div className="flex items-center gap-3">
            <Link
              href="/conversations"
              className="flex items-center gap-[6px] rounded-md px-[10px] py-[6px] text-[13px] font-medium text-[var(--text-secondary)]"
            >
              <ChevronLeft className="h-4 w-4" />
              返回列表
            </Link>

            <div className="h-6 w-px bg-[var(--border)]" />

            <span className="font-mono text-[13px] font-medium text-[var(--text-secondary)]">
              {id.slice(0, 8)}
            </span>

            {conv && (
              <>
                <span
                  className="flex items-center gap-1 rounded-full px-[10px] py-[3px]"
                  style={{
                    backgroundColor: STATUS_COLOR[conv.status as ConversationStatus].bg,
                  }}
                >
                  <span
                    className="h-[6px] w-[6px] rounded-full"
                    style={{ backgroundColor: STATUS_COLOR[conv.status as ConversationStatus].text }}
                  />
                  <span
                    className="text-[12px] font-medium"
                    style={{ color: STATUS_COLOR[conv.status as ConversationStatus].text }}
                  >
                    {STATUS_LABEL[conv.status as ConversationStatus]}
                  </span>
                </span>

                <span className="text-[16px] font-bold text-[var(--text-primary)]">
                  {conv.display_name || "—"}
                </span>
              </>
            )}
          </div>
        </header>

        {notFound ? (
          <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-secondary)]">
            找不到此對話
          </div>
        ) : error ? (
          <div className="m-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <div className="flex flex-1 overflow-hidden">
            <ChatTimeline messages={messages} loading={loading} />

            <aside className="flex w-[380px] flex-col gap-4 overflow-auto border-l border-[var(--border)] bg-[var(--bg-surface)] p-6">
              <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
                <h3 className="text-[14px] font-semibold text-[#18181B]">客戶資訊</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">顯示名稱</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv?.display_name || "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">LINE ID</span>
                    <span className="font-mono text-[12px] text-[#71717A]">
                      {conv?.line_user_id ? conv.line_user_id.slice(0, 12) + "…" : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
                <h3 className="text-[14px] font-semibold text-[#18181B]">對話資訊</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">狀態</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv ? STATUS_LABEL[conv.status as ConversationStatus] : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">訊息數</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv?.message_count ?? "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">解決層級</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv?.resolution_layer
                        ? RESOLUTION_LABEL[conv.resolution_layer] ?? "—"
                        : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">建立時間</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv ? formatRelative(conv.created_at) : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-[#A1A1AA]">最後更新</span>
                    <span className="text-[13px] font-medium text-[#18181B]">
                      {conv ? formatRelative(conv.updated_at) : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-[14px] font-semibold text-[#18181B]">關聯問題卡</h3>
                  {problemCards.length > 0 && (
                    <span className="text-[12px] text-[#A1A1AA]">
                      {problemCards.length} 張
                    </span>
                  )}
                </div>

                {pcError && (
                  <div className="rounded border border-red-200 bg-red-50 px-2 py-1 text-[11px] text-red-700">
                    載入失敗：{pcError}
                  </div>
                )}

                {pcLoading && problemCards.length === 0 && !pcError && (
                  <span className="text-[12px] text-[#A1A1AA]">載入中…</span>
                )}

                {!pcLoading && problemCards.length === 0 && !pcError && (
                  <span className="text-[12px] text-[#A1A1AA]">尚未建立問題卡</span>
                )}

                {problemCards.map((pc) => {
                  const style = PC_STATUS_LABEL[pc.status];
                  return (
                    <Link
                      key={pc.id}
                      href={`/problem-cards/${pc.id}`}
                      className="flex flex-col gap-1 rounded-md border border-[var(--border)] px-3 py-2 hover:bg-[#F8FAFC]"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[12px] font-semibold text-[var(--primary)]" title={pc.id}>
                          {pc.id.slice(0, 8)}
                        </span>
                        <span
                          className="rounded-full px-2 py-[1px] text-[11px] font-semibold"
                          style={{ color: style.color, backgroundColor: style.bg }}
                        >
                          {style.label}
                        </span>
                      </div>
                      <span className="text-[12px] text-[#18181B]">
                        {pc.brand || "—"} {pc.model || ""}
                      </span>
                      <span className="line-clamp-2 text-[11px] text-[#71717A]">
                        {pc.symptom || "（無症狀描述）"}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
