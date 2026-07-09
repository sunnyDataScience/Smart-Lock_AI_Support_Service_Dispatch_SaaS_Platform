"use client";

import { useEffect, useRef } from "react";

/**
 * BroadcastChannel 跨 tab 同步 hook。
 *
 * 用法：
 *   const broadcast = useBroadcast<NotifEvent>("smartlock.notifications", (msg) => {
 *     // 同 origin 其他 tab 廣播時收到，更新本地 state
 *   });
 *   // 主動廣播：
 *   broadcast.post({ type: "marked_read", id: "..." });
 *
 * - SSR safe（typeof window 檢查）
 * - 不會收到自己發的訊息（瀏覽器原生行為）
 * - 不需要清理：unmount 時自動 close
 */
export function useBroadcast<T = unknown>(
  channelName: string,
  onMessage?: (msg: T) => void,
): {
  post: (msg: T) => void;
} {
  const channelRef = useRef<BroadcastChannel | null>(null);
  const handlerRef = useRef(onMessage);

  useEffect(() => {
    handlerRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (typeof BroadcastChannel === "undefined") return; // 老瀏覽器 fallback：不啟用

    const ch = new BroadcastChannel(channelName);
    channelRef.current = ch;

    const handler = (ev: MessageEvent) => {
      handlerRef.current?.(ev.data as T);
    };
    ch.addEventListener("message", handler);

    return () => {
      ch.removeEventListener("message", handler);
      try {
        ch.close();
      } catch {
        // ignore
      }
      channelRef.current = null;
    };
  }, [channelName]);

  return {
    post: (msg: T) => {
      try {
        channelRef.current?.postMessage(msg);
      } catch {
        // ignore（chan 已關閉等情境）
      }
    },
  };
}

/**
 * 統一 channel 命名前綴，避免散在各處難以追蹤。
 */
export const BROADCAST_CHANNELS = {
  notifications: "smartlock.notifications",
  workOrder: (id: string) => `smartlock.work-order.${id}`,
} as const;

/**
 * 通知中心廣播事件型別
 */
export type NotificationBroadcastEvent =
  | { type: "marked_read"; id: string }
  | { type: "marked_unread"; id: string }
  | { type: "archived"; id: string }
  | { type: "all_read" }
  | { type: "new_received"; id: string };

/**
 * 工單廣播事件型別（同工單跨 tab）
 */
export type WorkOrderBroadcastEvent =
  | { type: "reschedule_submitted"; workOrderId: string }
  | { type: "reschedule_confirmed"; workOrderId: string }
  | { type: "completed"; workOrderId: string };
