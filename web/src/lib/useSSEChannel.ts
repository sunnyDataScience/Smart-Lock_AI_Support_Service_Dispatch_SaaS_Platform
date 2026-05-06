"use client";

import { useEffect, useRef, useState } from "react";
import { SSEMessage, SSEStatus, subscribeSSE } from "./sse";

/**
 * 訂閱單一 SSE 頻道的 React hook。對齊 useRealtimeChannel 的用法。
 */
export function useSSEChannel<T = unknown>(opts: {
  channelPath: string;
  enabled?: boolean;
  onMessage: (msg: SSEMessage<T>) => void;
  eventNames?: string[];
}): { status: SSEStatus } {
  const { channelPath, enabled = true, onMessage, eventNames } = opts;
  const [status, setStatus] = useState<SSEStatus>("idle");
  const handlerRef = useRef(onMessage);

  useEffect(() => {
    handlerRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!enabled || !channelPath) {
      setStatus("idle");
      return;
    }
    const unsubscribe = subscribeSSE<T>({
      channelPath,
      eventNames,
      onMessage: (msg) => handlerRef.current?.(msg),
      onStatusChange: setStatus,
    });
    return unsubscribe;
  }, [channelPath, enabled, eventNames]);

  return { status };
}
