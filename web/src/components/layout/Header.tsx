"use client";

import { useEffect, useState } from "react";
import { Search, Bell, RefreshCw } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Notification = components["schemas"]["Notification"];

interface NotificationListResponse {
  items?: Notification[];
  next_cursor?: string | null;
  has_more?: boolean;
  unread_count?: number;
}

interface HeaderProps {
  title: string;
  subtitle?: string;
}

const UNREAD_FETCH_LIMIT = 99;

function formatBadge(count: number, hasMore: boolean): string {
  if (hasMore || count > 99) return "99+";
  return String(count);
}

export default function Header({ title, subtitle }: HeaderProps) {
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<NotificationListResponse>(
          "/api/v1/notifications",
          { query: { status: "unread", limit: UNREAD_FETCH_LIMIT } },
        );
        if (cancelled) return;
        const fromCount = typeof res.unread_count === "number" ? res.unread_count : null;
        const fromItems = res.items?.length ?? 0;
        setUnreadCount(fromCount ?? fromItems);
        setHasMore(!!res.has_more);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
        setUnreadCount(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-[24px] font-semibold tracking-tight text-[#18181B]">
          {title}
        </h1>
        {subtitle && (
          <span className="text-[14px] text-[var(--text-secondary)]">
            {subtitle}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex w-[320px] items-center gap-2 rounded-xl border border-[#E4E4E7] px-3 py-0">
          <Search className="h-[18px] w-[18px] text-[#A1A1AA]" />
          <input
            type="text"
            placeholder="搜尋工單、技師、客戶..."
            className="h-10 flex-1 bg-transparent text-[14px] text-[#18181B] outline-none placeholder:text-[#A1A1AA]"
          />
        </div>

        <div
          className="h-[10px] w-[10px] rounded-full"
          style={{ backgroundColor: error ? "var(--error)" : "var(--success)" }}
          title={error ?? "API 連線正常"}
        />

        <button
          className="relative flex h-10 w-10 items-center justify-center rounded-lg"
          title={
            error
              ? `通知載入失敗：${error}`
              : unreadCount === null
                ? "載入中…"
                : `${unreadCount} 則未讀通知`
          }
        >
          <Bell className="h-5 w-5 text-[var(--text-secondary)]" />
          {unreadCount !== null && unreadCount > 0 && (
            <span className="absolute right-1 top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[var(--error)] px-1 text-[11px] font-semibold text-white">
              {formatBadge(unreadCount, hasMore)}
            </span>
          )}
        </button>

        <button className="flex h-10 w-10 items-center justify-center rounded-lg">
          <RefreshCw className="h-5 w-5 text-[var(--text-secondary)]" />
        </button>
      </div>
    </header>
  );
}
