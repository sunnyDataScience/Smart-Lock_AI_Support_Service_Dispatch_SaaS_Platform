/**
 * Server-Sent Events 訂閱層 — 對齊 docs/02-design/specs/asyncapi.yaml
 *
 * 設計：
 *   - 使用瀏覽器原生 EventSource，自動重連由瀏覽器處理
 *   - JWT 透過 query param 帶上（EventSource 不支援 custom header）
 *   - 預設訂閱 default channel；spec 定義的 message name 透過 onMessage 收
 *   - NEXT_PUBLIC_REALTIME_BASE_URL 未設 → silent disabled
 */

import { auth } from "./api";

const REALTIME_BASE_URL = process.env.NEXT_PUBLIC_REALTIME_BASE_URL ?? "";

export type SSEStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error"
  | "disabled";

export interface SSEMessage<T = unknown> {
  type?: string;
  payload?: T;
  [k: string]: unknown;
}

export interface SSESubscribeOptions<T = unknown> {
  /** 頻道路徑，例 "/realtime/diagnostics/<conv_id>" */
  channelPath: string;
  /** 收到 server 訊息（已 JSON.parse） */
  onMessage: (msg: SSEMessage<T>) => void;
  /** 連線狀態變更 */
  onStatusChange?: (status: SSEStatus) => void;
  /** 額外監聽特定事件名稱（spec name 例如 'diagnostic.reasoning.step'） */
  eventNames?: string[];
}

function toHttpBase(wsBase: string): string {
  return wsBase
    .replace(/^wss:\/\//, "https://")
    .replace(/^ws:\/\//, "http://")
    .replace(/\/$/, "");
}

export function subscribeSSE<T = unknown>(
  opts: SSESubscribeOptions<T>,
): () => void {
  const { channelPath, onMessage, onStatusChange, eventNames = [] } = opts;

  if (!REALTIME_BASE_URL) {
    onStatusChange?.("disabled");
    return () => {};
  }

  const tenantId = auth.getTenantId?.() ?? "";
  const token = auth.getAccessToken?.() ?? "";
  const base = toHttpBase(REALTIME_BASE_URL);
  const path = channelPath.startsWith("/") ? channelPath : `/${channelPath}`;
  const url = new URL(base + path);
  if (tenantId) url.searchParams.set("tenant_id", tenantId);
  if (token) url.searchParams.set("access_token", token);

  let cancelled = false;
  let source: EventSource | null = null;

  function setStatus(s: SSEStatus) {
    if (!cancelled) onStatusChange?.(s);
  }

  function handleData(data: string) {
    if (cancelled) return;
    try {
      const msg = JSON.parse(data) as SSEMessage<T>;
      onMessage(msg);
    } catch {
      // 容錯：spec 通常是 JSON，遇到非 JSON 直接忽略
    }
  }

  setStatus("connecting");
  try {
    source = new EventSource(url.toString());
  } catch {
    setStatus("error");
    return () => {};
  }

  source.onopen = () => {
    if (!cancelled) setStatus("open");
  };

  // default message channel
  source.onmessage = (ev) => handleData(ev.data);

  // named events from spec
  eventNames.forEach((name) => {
    source!.addEventListener(name, ((ev: MessageEvent) => {
      handleData(ev.data);
    }) as EventListener);
  });

  source.onerror = () => {
    if (cancelled) return;
    // EventSource 會自動重連；只在非預期關閉時改成 error / closed
    if (source?.readyState === EventSource.CLOSED) {
      setStatus("closed");
    } else {
      setStatus("error");
    }
  };

  return () => {
    cancelled = true;
    if (source) {
      try {
        source.close();
      } catch {
        // ignore
      }
      source = null;
    }
  };
}
