/**
 * Realtime WebSocket 訂閱層 — 對齊 docs/02-design/specs/asyncapi.yaml
 *
 * 設計（UAT R3-4 / R3-5 收斂後）：
 *   - 同一 channelPath 全站共用單一 WebSocket（模組級 registry），多個訂閱者
 *     共掛 handler —— 杜絕 StrictMode 雙掛載 / 快速 unmount-remount 產生殭屍
 *     socket 或漏 handler 的競態
 *   - access token 僅由 HttpOnly cookie 提供；URL 只帶非機密 tenant routing hint
 *   - 握手失敗（連線從未 open 就被關）時，先走既有 cookie refresh 機制
 *     再重連，避免過期 token 無限 403 重連
 *   - 自動重連 exponential backoff（1s → 2s → 5s → 10s → 30s, max 30s）
 *   - 最後一個訂閱者退訂後延遲 250ms 才拆線：StrictMode 立即重掛時重用連線
 *   - 後端未啟用時 silent disabled，不噴錯誤
 *
 * 使用：通常透過 React hook `useRealtimeChannel` 訂閱。手動使用見 subscribeRealtime。
 */

import { auth, tryRefreshAccessToken } from "./api";

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
  /** 連線錯誤記錄到 console（預設 false，dev 用） */
  logErrors?: boolean;
}

const BACKOFF_MS = [1000, 2000, 5000, 10000, 30000];

// 最後一個訂閱者退訂後的拆線延遲：StrictMode 的 unmount→remount 幾乎同步發生，
// 延遲一拍即可讓重掛者接手同一條連線，不產生「關了又開」的殭屍競態。
const TEARDOWN_LINGER_MS = 250;

type AnyHandler = (msg: RealtimeMessage) => void;
type StatusListener = (status: RealtimeStatus) => void;

interface ChannelEntry {
  channelPath: string;
  socket: WebSocket | null;
  status: RealtimeStatus;
  handlers: Set<AnyHandler>;
  statusListeners: Set<StatusListener>;
  retryCount: number;
  retryTimer: ReturnType<typeof setTimeout> | null;
  teardownTimer: ReturnType<typeof setTimeout> | null;
  /** 本次連線是否成功 open 過 —— false 即視為握手失敗（可能為 token 過期 403） */
  openedThisAttempt: boolean;
  /** entry 已拆除，忽略一切殘留事件 */
  closed: boolean;
  logErrors: boolean;
}

// 模組級 registry：同 channel 單一活躍連線（React 元件外的單例狀態）
const channels = new Map<string, ChannelEntry>();

/** 認證只走 HttpOnly cookie；URL 僅保留非機密 tenant routing hint。 */
function buildUrl(channelPath: string): string {
  const base = REALTIME_BASE_URL.replace(/\/$/, "");
  const path = channelPath.startsWith("/") ? channelPath : `/${channelPath}`;
  const url = new URL(base + path);
  const tenantId = auth.getTenantId?.() ?? "";
  if (tenantId) url.searchParams.set("tenant_id", tenantId);
  return url.toString();
}

function setStatus(entry: ChannelEntry, s: RealtimeStatus): void {
  if (entry.closed) return;
  entry.status = s;
  for (const listener of [...entry.statusListeners]) {
    try {
      listener(s);
    } catch (e) {
      if (entry.logErrors) console.warn("[realtime] status listener failed", e);
    }
  }
}

function scheduleReconnect(entry: ChannelEntry): void {
  if (entry.closed || entry.retryTimer) return;
  const delay = BACKOFF_MS[Math.min(entry.retryCount, BACKOFF_MS.length - 1)];
  entry.retryCount += 1;
  const handshakeFailed = !entry.openedThisAttempt;
  entry.retryTimer = setTimeout(() => {
    entry.retryTimer = null;
    if (entry.closed) return;
    if (handshakeFailed) {
      // 握手失敗（常見根因：access cookie 已過期 → 403）：先走既有 refresh
      // 機制換新 cookie 再重連。refresh 失敗也照樣重連；若其他 REST 請求已
      // 刷新成功即可直接受益。
      void tryRefreshAccessToken()
        .catch(() => false)
        .then(() => {
          if (!entry.closed) connect(entry);
        });
    } else {
      connect(entry);
    }
  }, delay);
}

function connect(entry: ChannelEntry): void {
  if (entry.closed) return;
  entry.openedThisAttempt = false;
  setStatus(entry, "connecting");

  let socket: WebSocket;
  try {
    socket = new WebSocket(buildUrl(entry.channelPath));
  } catch (e) {
    if (entry.logErrors) console.warn("[realtime] WS construct failed", e);
    setStatus(entry, "error");
    scheduleReconnect(entry);
    return;
  }
  entry.socket = socket;

  socket.onopen = () => {
    if (entry.closed || entry.socket !== socket) {
      try {
        socket.close();
      } catch {
        // ignore
      }
      return;
    }
    entry.retryCount = 0;
    entry.openedThisAttempt = true;
    setStatus(entry, "open");
  };

  socket.onmessage = (ev) => {
    if (entry.closed || entry.socket !== socket) return;
    let data: RealtimeMessage;
    try {
      data =
        typeof ev.data === "string"
          ? (JSON.parse(ev.data) as RealtimeMessage)
          : (ev.data as RealtimeMessage);
    } catch (e) {
      if (entry.logErrors) console.warn("[realtime] parse failed", e, ev.data);
      return;
    }
    // 快照後逐一派發：任一 handler 拋錯不影響其他訂閱者
    for (const handler of [...entry.handlers]) {
      try {
        handler(data);
      } catch (e) {
        if (entry.logErrors) console.warn("[realtime] handler failed", e);
      }
    }
  };

  socket.onerror = () => {
    if (entry.closed || entry.socket !== socket) return;
    if (entry.logErrors) console.warn("[realtime] WS error", entry.channelPath);
    setStatus(entry, "error");
  };

  socket.onclose = () => {
    if (entry.closed || entry.socket !== socket) return;
    entry.socket = null;
    // 真實回報斷線狀態（R3-4：斷線時指示燈必須反映），並排程重連
    setStatus(entry, "closed");
    scheduleReconnect(entry);
  };
}

function teardown(channelPath: string): void {
  const entry = channels.get(channelPath);
  if (!entry) return;
  // linger 期間有人重新訂閱 → 保留連線
  if (entry.handlers.size > 0 || entry.statusListeners.size > 0) {
    entry.teardownTimer = null;
    return;
  }
  entry.closed = true;
  if (entry.retryTimer) clearTimeout(entry.retryTimer);
  if (entry.teardownTimer) clearTimeout(entry.teardownTimer);
  const socket = entry.socket;
  entry.socket = null;
  if (socket) {
    try {
      socket.close(1000, "client_unsubscribe");
    } catch {
      // ignore
    }
  }
  channels.delete(channelPath);
}

export function subscribeRealtime<T = unknown>(
  opts: RealtimeSubscribeOptions<T>,
): () => void {
  const { channelPath, onMessage, onStatusChange, logErrors = false } = opts;

  if (!REALTIME_BASE_URL) {
    onStatusChange?.("disabled");
    return () => {};
  }

  const handler = onMessage as AnyHandler;
  const statusListener = onStatusChange as StatusListener | undefined;

  let entry = channels.get(channelPath);
  if (!entry) {
    entry = {
      channelPath,
      socket: null,
      status: "idle",
      handlers: new Set([handler]),
      statusListeners: new Set(statusListener ? [statusListener] : []),
      retryCount: 0,
      retryTimer: null,
      teardownTimer: null,
      openedThisAttempt: false,
      closed: false,
      logErrors,
    };
    channels.set(channelPath, entry);
    connect(entry);
  } else {
    // 既有連線：取消待拆除、掛上 handler、立刻回報當前狀態
    if (entry.teardownTimer) {
      clearTimeout(entry.teardownTimer);
      entry.teardownTimer = null;
    }
    entry.handlers.add(handler);
    if (statusListener) {
      entry.statusListeners.add(statusListener);
      statusListener(entry.status);
    }
    if (logErrors) entry.logErrors = true;
  }

  let unsubscribed = false;
  return () => {
    if (unsubscribed) return;
    unsubscribed = true;
    const e = channels.get(channelPath);
    if (!e || e.closed) return;
    e.handlers.delete(handler);
    if (statusListener) e.statusListeners.delete(statusListener);
    if (e.handlers.size === 0 && e.statusListeners.size === 0 && !e.teardownTimer) {
      e.teardownTimer = setTimeout(() => teardown(channelPath), TEARDOWN_LINGER_MS);
    }
  };
}

export function isRealtimeEnabled(): boolean {
  return !!REALTIME_BASE_URL;
}
