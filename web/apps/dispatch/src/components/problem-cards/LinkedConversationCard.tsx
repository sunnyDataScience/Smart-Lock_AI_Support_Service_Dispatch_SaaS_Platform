"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { ApiError, api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { formatRelative } from "@shared/lib/format";
import type { components } from "@shared/types/api.generated";

type Conversation = components["schemas"]["Conversation"];
type ConversationEnvelope = components["schemas"]["ConversationEnvelope"];
type Message = components["schemas"]["Message"];
type MessagePage = components["schemas"]["MessagePage"];

interface Props {
  conversationId?: string | null;
}

const PREVIEW_LIMIT = 6;

function UserMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex w-full justify-end">
      <div className="flex max-w-[320px] flex-col gap-[6px] rounded-bl-xl rounded-br-xl rounded-tl-xl rounded-tr bg-[#EFF6FF] px-[14px] py-[10px]">
        <span className="whitespace-pre-line text-[13px] text-[var(--text-primary)]">
          {msg.content}
        </span>
        <span className="text-right text-[11px] text-[var(--text-secondary)]">
          {formatRelative(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

function AiMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex gap-2">
      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-[14px] bg-[#2563EB]">
        <span className="text-[11px] font-bold text-white">AI</span>
      </div>
      <div className="flex max-w-[320px] flex-col gap-[6px] rounded-bl-xl rounded-br-xl rounded-tl rounded-tr-xl bg-[#F8FAFC] px-[14px] py-[10px]">
        <span className="whitespace-pre-line text-[13px] text-[var(--text-primary)]">
          {msg.content}
        </span>
        <span className="text-[11px] text-[var(--text-secondary)]">
          {formatRelative(msg.created_at)} · AI 助理
        </span>
      </div>
    </div>
  );
}

function SystemMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex w-full justify-center">
      <span className="text-[12px] italic text-[var(--text-disabled)]">
        系統：{msg.content}
      </span>
    </div>
  );
}

export default function LinkedConversationCard({ conversationId }: Props) {
  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conversationId) {
      setConv(null);
      setMessages([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [envelope, page] = await Promise.all([
          api.get<ConversationEnvelope>(
            tenantPath(`/conversations/${encodeURIComponent(conversationId)}`),
          ),
          api.get<MessagePage>(
            tenantPath(`/conversations/${encodeURIComponent(conversationId)}/messages`),
            { query: { limit: PREVIEW_LIMIT } },
          ),
        ]);
        if (cancelled) return;
        setConv(envelope.data ?? null);
        setMessages(page.items ?? []);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? friendlyError(e)
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

  const ordered = [...messages].reverse();
  const totalCount = conv?.message_count ?? messages.length;
  const headerLabel = conversationId
    ? `關聯對話紀錄（${totalCount} 則訊息${
        messages.length < totalCount ? "，預覽前 " + messages.length + " 則" : ""
      }）`
    : "關聯對話紀錄";

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <ChevronDown className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            {headerLabel}
          </span>
        </div>
        {conversationId ? (
          <Link
            href={`/conversations/${conversationId}`}
            className="text-[13px] font-medium text-[#2563EB] hover:underline"
          >
            在對話管理中檢視完整紀錄 →
          </Link>
        ) : (
          <span className="text-[13px] text-[var(--text-disabled)]">無關聯對話</span>
        )}
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      <div className="flex flex-col gap-4 px-6 py-5">
        {!conversationId ? (
          <p className="text-center text-[13px] text-[var(--text-secondary)]">
            此問題卡未連結至任何對話
          </p>
        ) : loading ? (
          <p className="text-center text-[13px] text-[var(--text-secondary)]">
            載入中…
          </p>
        ) : error ? (
          <p className="text-center text-[13px] text-red-600">載入失敗：{error}</p>
        ) : ordered.length === 0 ? (
          <p className="text-center text-[13px] text-[var(--text-secondary)]">
            尚無訊息
          </p>
        ) : (
          <>
            {conv && (
              <p className="text-center text-[12px] text-[var(--text-secondary)]">
                {formatRelative(conv.created_at)} · {conv.display_name || "—"}
              </p>
            )}
            {ordered.map((m) => {
              if (m.role === "user") return <UserMessage key={m.id} msg={m} />;
              if (m.role === "assistant") return <AiMessage key={m.id} msg={m} />;
              return <SystemMessage key={m.id} msg={m} />;
            })}
          </>
        )}
      </div>
    </div>
  );
}
