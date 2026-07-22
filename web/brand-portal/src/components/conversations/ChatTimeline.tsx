"use client";

import { useEffect, useRef } from "react";
import { Headset, ImageOff, Sparkles } from "lucide-react";
import { AuthImage } from "@/components/media/AuthImage";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Message = components["schemas"]["Message"];

/**
 * 對話照片（CR-0119）：media_url 指向 GET /api/v1/media/{id}，端點需
 * Bearer token + X-Tenant-ID，<img src> 直連會 401。
 * CR-0178 輪次 C：fetch→blob 邏輯抽至共用 <AuthImage>（media/AuthImage.tsx），
 * 此處僅保留深色泡泡配色的佔位（thin wrapper，避免同款程式碼第 4 份複本）。
 */
function AuthChatImage({ url, alt }: { url: string; alt: string }) {
  return (
    <AuthImage
      url={url}
      alt={alt}
      className="max-h-[240px] rounded-md"
      errorNode={
        <div className="flex items-center gap-1 rounded-md bg-white/15 px-3 py-2 text-[12px] text-white/80">
          <ImageOff className="h-4 w-4" />
          照片載入失敗
        </div>
      }
      loadingNode={
        <div className="flex h-[160px] w-[220px] items-center justify-center rounded-md bg-white/15 text-[12px] text-white/70">
          照片載入中…
        </div>
      }
    />
  );
}

function CustomerMessage({ msg, idx }: { msg: Message; idx: number }) {
  // 照片已顯示時，「[照片]」佔位文字是冗餘（無 media_url 的歷史訊息仍顯示文字）
  const showText =
    !!msg.content && !(msg.media_url && msg.content.trim() === "[照片]");
  return (
    <div className="flex w-full justify-end">
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[522px] rounded-[16px_4px_16px_16px] bg-[var(--primary)] px-4 py-3 text-white">
          {msg.media_url && (
            <div className={showText ? "mb-2" : ""}>
              <AuthChatImage
                url={msg.media_url}
                alt={`客人上傳的照片 #${idx + 1}`}
              />
            </div>
          )}
          {showText && (
            <p className="whitespace-pre-line text-[15px] leading-[1.5]">
              {msg.content}
            </p>
          )}
        </div>
        <span className="text-[12px] text-[var(--text-disabled)]">
          {formatRelative(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

function AiMessage({ msg }: { msg: Message }) {
  // UAT W5-1：接管中真人客服發送的訊息（metadata.sender_role=agent_human）需與
  // AI 助理視覺區分（稽核/交接要能分辨真人發言）。metadata 為加法欄位，
  // api.generated 型別尚未帶出前先防禦性讀取。
  const senderRole = (
    msg as Message & { metadata?: { sender_role?: string } | null }
  ).metadata?.sender_role;
  const isHumanAgent = senderRole === "agent_human";
  return (
    <div className="flex w-full flex-col gap-[6px]">
      <div className="flex items-center gap-[6px]">
        <div
          className={`flex h-6 w-6 items-center justify-center rounded-full ${
            isHumanAgent ? "bg-[#ECFDF5]" : "bg-[#EFF6FF]"
          }`}
          aria-hidden="true"
        >
          {isHumanAgent ? (
            <Headset className="h-[14px] w-[14px] text-[#047857]" />
          ) : (
            <Sparkles className="h-[14px] w-[14px] text-[var(--primary)]" />
          )}
        </div>
        <span
          data-testid={isHumanAgent ? "msg-sender-human" : "msg-sender-ai"}
          className={`text-[12px] font-semibold ${
            isHumanAgent ? "text-[#047857]" : "text-[var(--primary)]"
          }`}
        >
          {isHumanAgent ? "客服人員" : "AI 助理"}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        <div className="overflow-hidden rounded-[4px_16px_16px_16px] border-[1.5px] border-[var(--border)]">
          <div className="px-4 py-3">
            <p className="max-w-[490px] whitespace-pre-line text-[15px] leading-[1.5] text-[#18181B]">
              {msg.content}
            </p>
          </div>
        </div>
        <span className="text-[12px] text-[var(--text-disabled)]">
          {formatRelative(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

function SystemMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex w-full justify-center">
      <div className="rounded-lg bg-[#F1F5F9] px-4 py-[6px]">
        <span className="text-[12px] text-[var(--text-tertiary)]">{msg.content}</span>
      </div>
    </div>
  );
}

interface Props {
  messages: Message[];
  loading?: boolean;
}

export default function ChatTimeline({ messages, loading = false }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // API returns DESC; render ASC for natural chat flow.
  const ordered = [...messages].reverse();
  // 自動捲到最底：初次載入、refetch、客服送出新訊息（messages 變動）都觸發。
  // 依「訊息數 + 最後一則 id」當 key，避免同筆資料重複捲動。
  const lastId = ordered.length ? ordered[ordered.length - 1].id : null;
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, lastId]);

  if (loading && messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[var(--bg-page)] text-sm text-[var(--text-secondary)]">
        載入中…
      </div>
    );
  }
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[var(--bg-page)] text-sm text-[var(--text-secondary)]">
        尚無訊息
      </div>
    );
  }
  return (
    <div
      ref={scrollRef}
      role="log"
      aria-label="對話訊息列表"
      aria-live="polite"
      aria-relevant="additions"
      className="flex flex-1 flex-col gap-6 overflow-auto bg-[var(--bg-page)] p-6"
    >
      {ordered.map((m, idx) => {
        if (m.role === "user")
          return <CustomerMessage key={m.id} msg={m} idx={idx} />;
        if (m.role === "assistant") return <AiMessage key={m.id} msg={m} />;
        return <SystemMessage key={m.id} msg={m} />;
      })}
    </div>
  );
}
