"use client";

import { useEffect, useRef, useState } from "react";
import {
  RealtimeMessage,
  RealtimeStatus,
  subscribeRealtime,
} from "@/lib/realtime";

/**
 * 訂閱單一 realtime 頻道的 React hook。
 *
 * 用法：
 *   useRealtimeChannel<NotificationEvent>({
 *     channelPath: `/realtime/notifications/${userId}`,
 *     enabled: !!userId,
 *     onMessage: (msg) => { ... },
 *   });
 *
 * - enabled=false 時不訂閱（也不顯示 disabled 狀態）
 * - channelPath 變更時自動重新訂閱
 * - StrictMode 下的雙重執行透過 cancelled flag 處理
 */
export function useRealtimeChannel<T = unknown>(opts: {
  channelPath: string;
  enabled?: boolean;
  onMessage: (msg: RealtimeMessage<T>) => void;
}): { status: RealtimeStatus } {
  const { channelPath, enabled = true, onMessage } = opts;
  const [status, setStatus] = useState<RealtimeStatus>("idle");
  const handlerRef = useRef(onMessage);

  useEffect(() => {
    handlerRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!enabled || !channelPath) {
      setStatus("idle");
      return;
    }
    const unsubscribe = subscribeRealtime<T>({
      channelPath,
      onMessage: (msg) => handlerRef.current?.(msg),
      onStatusChange: setStatus,
    });
    return unsubscribe;
  }, [channelPath, enabled]);

  return { status };
}
