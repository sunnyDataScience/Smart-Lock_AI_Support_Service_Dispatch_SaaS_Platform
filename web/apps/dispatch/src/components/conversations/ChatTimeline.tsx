"use client";

import { useEffect, useRef, useState } from "react";
import { ImageOff, Sparkles } from "lucide-react";
import { auth } from "@shared/lib/api";
import { formatRelative } from "@shared/lib/format";
import type { components } from "@shared/types/api.generated";

type Message = components["schemas"]["Message"];

/**
 * 對話照片（CR-0119）：media_url 指向 GET /api/v1/media/{id}，端點需
 * Bearer token + X-Tenant-ID，<img src> 直連會 401。比照 MediaGallery 的
 * 「帶 token fetch → blob URL」模式顯示；絕對 URL（日後 GCS 簽名 URL）直接用。
 */
function AuthChatImage({ url, alt }: { url: string; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    setFailed(false);
    if (/^https?:\/\//.test(url)) {
      setSrc(url);
      return;
    }
    let cancelled = false;
    const ac = new AbortController();
    // || 而非 ??：docker build 會把未設的 env 烘成空字串，?? 接不住（lib/api.ts 同款）
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";
    const token = auth.getAccessToken();

    (async () => {
      try {
        const res = await fetch(`${baseUrl}${url}`, {
          headers: {
            Authorization: token ? `Bearer ${token}` : "",
            "X-Tenant-ID": auth.getTenantId(),
          },
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        objectUrlRef.current = objUrl;
        if (!cancelled) setSrc(objUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      ac.abort();
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [url]);

  if (failed) {
    return (
      <div className="flex items-center gap-1 rounded-md bg-white/15 px-3 py-2 text-[12px] text-white/80">
        <ImageOff className="h-4 w-4" />
        照片載入失敗
      </div>
    );
  }
  if (!src) {
    return (
      <div className="flex h-[160px] w-[220px] items-center justify-center rounded-md bg-white/15 text-[12px] text-white/70">
        照片載入中…
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} decoding="async" className="max-h-[240px] rounded-md" />
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
