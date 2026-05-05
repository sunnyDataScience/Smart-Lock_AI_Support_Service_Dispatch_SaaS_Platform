"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import {
  BROADCAST_CHANNELS,
  NotificationBroadcastEvent,
  useBroadcast,
} from "@/lib/useBroadcast";
import type { components } from "@/types/api.generated";
import NotificationDrawer from "./NotificationDrawer";

type Notification = components["schemas"]["Notification"];

interface NotificationListResponse {
  items?: Notification[];
  next_cursor?: string | null;
  has_more?: boolean;
  unread_count?: number;
}

interface Props {
  /** 顯示樣式：dark = 深色背景（如 Sidebar），light = 淺色背景（預設）。 */
  variant?: "light" | "dark";
}

const UNREAD_FETCH_LIMIT = 99;

function formatBadge(count: number, hasMore: boolean): string {
  if (hasMore || count > 99) return "99+";
  return String(count);
}

export default function NotificationBell({ variant = "light" }: Props) {
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const refreshBadge = useCallback(async () => {
    try {
      const res = await api.get<NotificationListResponse>(
        "/api/v1/notifications",
        { query: { status: "unread", limit: UNREAD_FETCH_LIMIT } },
      );
      const fromCount =
        typeof res.unread_count === "number" ? res.unread_count : null;
      const fromItems = res.items?.length ?? 0;
      setUnreadCount(fromCount ?? fromItems);
      setHasMore(!!res.has_more);
      setError(null);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
      setUnreadCount(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await refreshBadge();
      if (cancelled) return;
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshBadge]);

  // 跨 tab 同步：其他 tab 標記已讀/全部已讀/封存/收新通知時，更新 bell 紅點
  useBroadcast<NotificationBroadcastEvent>(
    BROADCAST_CHANNELS.notifications,
    (event) => {
      if (event.type === "marked_read") {
        setUnreadCount((c) => (c == null ? c : Math.max(0, c - 1)));
      } else if (event.type === "all_read") {
        setUnreadCount(0);
        setHasMore(false);
      } else if (event.type === "new_received") {
        setUnreadCount((c) => (c == null ? 1 : c + 1));
      } else if (event.type === "archived") {
        // 封存若為未讀也減少 badge（保守不減，等 refresh 校正）
        refreshBadge();
      }
    },
  );

  const iconColor =
    variant === "dark"
      ? "text-white"
      : "text-[var(--text-secondary)]";
  const hoverBg =
    variant === "dark" ? "hover:bg-[#334155]" : "hover:bg-[#F1F5F9]";

  return (
    <>
      <button
        type="button"
        onClick={() => setDrawerOpen(true)}
        className={`relative flex h-10 w-10 items-center justify-center rounded-lg ${hoverBg}`}
        title={
          error
            ? `通知載入失敗：${error}`
            : unreadCount === null
              ? "載入中…"
              : `${unreadCount} 則未讀通知`
        }
        aria-label="開啟通知中心"
      >
        <Bell className={`h-5 w-5 ${iconColor}`} />
        {unreadCount !== null && unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[var(--error)] px-1 text-[11px] font-semibold text-white">
            {formatBadge(unreadCount, hasMore)}
          </span>
        )}
      </button>

      <NotificationDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          refreshBadge();
        }}
        onUnreadCountChange={(count, more) => {
          setUnreadCount(count);
          setHasMore(more);
        }}
      />
    </>
  );
}
