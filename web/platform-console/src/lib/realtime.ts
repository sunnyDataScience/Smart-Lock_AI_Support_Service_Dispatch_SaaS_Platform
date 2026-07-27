/**
 * Realtime WebSocket 訂閱層 — 對齊 docs/02-design/specs/asyncapi.yaml
 *
 * 設計：
 *   - 一個 channelPath 對應一個獨立 WebSocket（簡化 server-side 路由）
 *   - 自動重連 exponential backoff（1s → 2s → 5s → 10s → 30s, max 30s）
 *   - 認證只走 HttpOnly cookie；URL 只帶非機密 tenant routing hint
 *   - 後端未啟用時 silent disabled，不噴錯誤
 *
 * 使用：通常透過 React hook `useRealtimeChannel` 訂閱。手動使用見 subscribeRealtime。
 */

import { auth } from "./api";

const REALTIME_BASE_URL = process.env.NEXT_PUBLIC_REALTIME_BASE_URL ?? "";

export type RealtimeStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error"
  | "disabled";

export interface RealtimeMessage<T = unknown> {
  type?: string;
  payload?: T;
  timestamp?: string;
  [k: string]: unknown;
}

export interface RealtimeSubscribeOptions<T = unknown> {
  /** 頻道路徑，例 "/realtime/notifications/<user_id>"。會自動拼接到 NEXT_PUBLIC_REALTIME_BASE_URL。 */
  channelPath: string;
  /** 收到 server 訊息的 callback（已 JSON.parse） */
  onMessage: (msg: RealtimeMessage<T>) => void;
  /** 連線狀態變更（含 disabled 表示未設 base url） */
  onStatusChange?: (status: RealtimeStatus) => void;
  /** 連線錯誤記錄到 console（預設 true，dev 用） */
  logErrors?: boolean;
}

const BACKOFF_MS = [1000, 2000, 5000, 10000, 30000];

export function subscribeRealtime<T = unknown>(
  opts: RealtimeSubscribeOptions<T>,
): () => void {
  const { channelPath, onMessage, onStatusChange, logErrors = false } = opts;

  if (!REALTIME_BASE_URL) {
    onStatusChange?.("disabled");
    return () => {};
  }

  let cancelled = false;
  let socket: WebSocket | null = null;
  let retryCount = 0;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const tenantId = auth.getTenantId?.() ?? "";
  function buildUrl(): string {
    const base = REALTIME_BASE_URL.replace(/\/$/, "");
    const path = channelPath.startsWith("/") ? channelPath : `/${channelPath}`;
    const url = new URL(base + path);
    if (tenantId) url.searchParams.set("tenant_id", tenantId);
    return url.toString();
  }

  function setStatus(s: RealtimeStatus) {
    if (cancelled) return;
    onStatusChange?.(s);
  }

  function scheduleReconnect() {
    if (cancelled) return;
    const delay = BACKOFF_MS[Math.min(retryCount, BACKOFF_MS.length - 1)];
    retryCount += 1;
    retryTimer = setTimeout(connect, delay);
  }

  function connect() {
    if (cancelled) return;
    setStatus("connecting");
    try {
      socket = new WebSocket(buildUrl());
    } catch (e) {
      if (logErrors) console.warn("[realtime] WS construct failed", e);
      setStatus("error");
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      if (cancelled) {
        socket?.close();
        return;
      }
      retryCount = 0;
      setStatus("open");
    };

    socket.onmessage = (ev) => {
      if (cancelled) return;
      try {
        const data: RealtimeMessage<T> =
          typeof ev.data === "string"
            ? (JSON.parse(ev.data) as RealtimeMessage<T>)
            : (ev.data as RealtimeMessage<T>);
        onMessage(data);
      } catch (e) {
        if (logErrors) console.warn("[realtime] parse failed", e, ev.data);
      }
    };

    socket.onerror = () => {
      if (logErrors) console.warn("[realtime] WS error", channelPath);
      setStatus("error");
    };

    socket.onclose = () => {
      if (cancelled) return;
      setStatus("closed");
      socket = null;
      scheduleReconnect();
    };
  }

  connect();

  return () => {
    cancelled = true;
    if (retryTimer) clearTimeout(retryTimer);
    if (socket) {
      try {
        socket.close(1000, "client_unsubscribe");
      } catch {
        // ignore
      }
      socket = null;
    }
  };
}

export function isRealtimeEnabled(): boolean {
  return !!REALTIME_BASE_URL;
}
