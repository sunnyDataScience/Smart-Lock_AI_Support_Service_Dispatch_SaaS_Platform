"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { api, getCurrentSession, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useRealtimeChannel } from "@/hooks/useRealtimeChannel";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import {
  BROADCAST_CHANNELS,
  NotificationBroadcastEvent,
  useBroadcast,
} from "@/hooks/useBroadcast";
import type { components } from "@/types/api.generated";
import NotificationDrawer from "./NotificationDrawer";

import type { Notification } from "@/types/api.local";

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
  const t = useTranslations("components.notificationBell");
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const refreshBadge = useCallback(async () => {
    try {
      const res = await api.get<NotificationListResponse>(
        tenantPath("/notifications"),
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
        friendlyError(e),
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

  // UAT W5-2：通知即時推播 —— 訂閱 /realtime/notifications/{user_id} WS
  // （後端 push_notification 寫 DB 後 publish 至同一 hub；payload=通知 JSON）。
  // 收到訊息 → refreshBadge（refetch，不依賴推送計數，UAT R3-4）；
  // 抽屜開啟時透過既有 broadcast 事件觸發清單刷新。
  // 斷線重連（exponential backoff）由 subscribeRealtime 內建，靜默處理。
  const broadcast = useBroadcast<NotificationBroadcastEvent>(
    BROADCAST_CHANNELS.notifications,
  );
  // UAT R3-4 根因之一：原 useMemo(..., []) 在首次 render 讀 session，claims cookie
  // 尚未就緒時鎖死 null → 該 session 永不訂閱 WS（間歇失效）。改 effect 讀取。
  const [userId, setUserId] = useState<string | null>(null);
  useEffect(() => {
    setUserId(getCurrentSession()?.userId ?? null);
  }, []);
  useRealtimeChannel<Notification>({
    channelPath: userId ? `/realtime/notifications/${userId}` : "",
    enabled: !!userId,
    onMessage: (msg) => {
      const incoming = (msg.payload ?? msg) as Notification | undefined;
      refreshBadge();
      if (incoming?.id) {
        // NotificationDrawer 監聽同名 BroadcastChannel（不同 channel 實例，
        // 同分頁也收得到）→ 抽屜開啟時 fetchItems 刷新清單
        broadcast.post({ type: "new_received", id: incoming.id });
      }
    },
  });

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
        className={`relative flex h-10 w-10 items-center justify-center rounded-lg focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 ${hoverBg}`}
        title={
          error
            ? t("loadError", { error })
            : unreadCount === null
              ? t("loadingTitle")
              : t("unreadTitle", { count: String(unreadCount) })
        }
        aria-label={
          error
            ? t("loadError", { error })
            : unreadCount === null
              ? t("ariaLoading")
              : unreadCount > 0
                ? t("ariaUnread", { count: String(unreadCount) })
                : t("ariaNone")
        }
        aria-haspopup="dialog"
        aria-expanded={drawerOpen}
      >
        <Bell className={`h-5 w-5 ${iconColor}`} aria-hidden="true" />
        {unreadCount !== null && unreadCount > 0 && (
          <span
            className="absolute right-1 top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[var(--error)] px-1 text-[11px] font-semibold text-white"
            aria-hidden="true"
          >
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
