"use client";

import { useEffect, useRef } from "react";
import { Sparkles } from "lucide-react";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Message = components["schemas"]["Message"];

function CustomerMessage({ msg, idx }: { msg: Message; idx: number }) {
  return (
    <div className="flex w-full justify-end">
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[522px] rounded-[16px_4px_16px_16px] bg-[var(--primary)] px-4 py-3 text-white">
          {msg.media_url && (
            <div className="mb-2">
              {/*
                媒體 URL 為 LINE / GCS 動態簽名 URL，尺寸不固定，
                不適合 next/image（會浪費 image optimization service quota）。
                用原生 img + lazy load + async decode：免阻塞主執行緒、
                可視範圍外不下載。alt 後綴序號讓 screen reader 能區分多媒體訊息。
              */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={msg.media_url}
                alt={`使用者上傳的媒體 #${idx + 1}`}
                loading="lazy"
                decoding="async"
                className="max-h-[240px] rounded-md"
              />
            </div>
          )}
          <p className="whitespace-pre-line text-[15px] leading-[1.5]">
            {msg.content}
          </p>
        </div>
        <span className="text-[12px] text-[var(--text-disabled)]">
          {formatRelative(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

function AiMessage({ msg }: { msg: Message }) {
  return (
    <div className="flex w-full flex-col gap-[6px]">
      <div className="flex items-center gap-[6px]">
        <div
          className="flex h-6 w-6 items-center justify-center rounded-full bg-[#EFF6FF]"
          aria-hidden="true"
        >
          <Sparkles className="h-[14px] w-[14px] text-[var(--primary)]" />
        </div>
        <span className="text-[12px] font-semibold text-[var(--primary)]">
          AI 助理
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
