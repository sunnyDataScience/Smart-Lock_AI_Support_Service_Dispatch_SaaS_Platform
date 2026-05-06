"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell,
  X,
  CheckCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { ApiError, api } from "@/lib/api";
import {
  BROADCAST_CHANNELS,
  NotificationBroadcastEvent,
  useBroadcast,
} from "@/lib/useBroadcast";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Notification = components["schemas"]["Notification"];
type NotificationSeverity = components["schemas"]["NotificationSeverity"];
type NotificationType = components["schemas"]["NotificationType"];

interface NotificationListResponse {
  items?: Notification[];
  next_cursor?: string | null;
  has_more?: boolean;
  unread_count?: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onUnreadCountChange?: (count: number, hasMore: boolean) => void;
}

type StatusFilter = "unread" | "all";

const PAGE_LIMIT = 50;

const SEVERITY_META: Record<
  NotificationSeverity,
  {
    color: string;
    bg: string;
    Icon: React.ComponentType<{
      className?: string;
      style?: React.CSSProperties;
    }>;
  }
> = {
  info: { color: "#2563EB", bg: "#EFF6FF", Icon: Info },
  warning: { color: "#D97706", bg: "#FEF3C7", Icon: AlertTriangle },
  critical: { color: "#DC2626", bg: "#FEE2E2", Icon: AlertCircle },
};

const TYPE_LABEL: Record<NotificationType, string> = {
  work_order: "工單",
  refund: "退款",
  dispute: "爭議",
  rbac: "權限",
  inventory: "庫存",
  sla: "SLA",
  system: "系統",
  mention: "提及",
};

const TABS: { value: StatusFilter; label: string }[] = [
  { value: "unread", label: "未讀" },
  { value: "all", label: "全部" },
];

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function NotificationDrawer({
  open,
  onClose,
  onUnreadCountChange,
}: Props) {
  const [tab, setTab] = useState<StatusFilter>("unread");
  const [items, setItems] = useState<Notification[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const fetchItems = useCallback(
    async (status: StatusFilter) => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number> = { limit: PAGE_LIMIT };
        if (status === "unread") query.status = "unread";
        const res = await api.get<NotificationListResponse>(
          "/api/v1/notifications",
          { query },
        );
        const next = res.items ?? [];
        setItems(next);
        setHasMore(!!res.has_more);
        if (status === "unread" && onUnreadCountChange) {
          const fromCount =
            typeof res.unread_count === "number" ? res.unread_count : null;
          onUnreadCountChange(fromCount ?? next.length, !!res.has_more);
        }
      } catch (e) {
        setError(formatErr(e));
      } finally {
        setLoading(false);
      }
    },
    [onUnreadCountChange],
  );

  useEffect(() => {
    if (!open) return;
    fetchItems(tab);
  }, [open, tab, fetchItems]);

  // 跨 tab 同步：其他 tab 操作時，drawer 開啟時即時刷新本地列表
  const broadcast = useBroadcast<NotificationBroadcastEvent>(
    BROADCAST_CHANNELS.notifications,
    (event) => {
      if (!open) return;
      if (event.type === "marked_read") {
        const now = new Date().toISOString();
        setItems((prev) =>
          prev.map((x) =>
            x.id === event.id && !x.read_at ? { ...x, read_at: now } : x,
          ),
        );
        if (tab === "unread") {
          setItems((prev) => prev.filter((x) => x.id !== event.id));
        }
      } else if (event.type === "archived") {
        setItems((prev) => prev.filter((x) => x.id !== event.id));
      } else if (event.type === "all_read") {
        if (tab === "unread") setItems([]);
        else {
          const now = new Date().toISOString();
          setItems((prev) =>
            prev.map((x) => (x.read_at ? x : { ...x, read_at: now })),
          );
        }
        onUnreadCountChange?.(0, false);
      } else if (event.type === "new_received") {
        fetchItems(tab);
      }
    },
  );

  async function markOneRead(n: Notification) {
    if (n.read_at || marking) return;
    setMarking(n.id);
    setError(null);
    try {
      await api.patch(`/api/v1/notifications/${encodeURIComponent(n.id)}`, {
        read_at: new Date().toISOString(),
      });
      if (tab === "unread") {
        setItems((prev) => prev.filter((x) => x.id !== n.id));
      } else {
        setItems((prev) =>
          prev.map((x) =>
            x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x,
          ),
        );
      }
      if (onUnreadCountChange) {
        const remaining = items.filter(
          (x) => !x.read_at && x.id !== n.id,
        ).length;
        onUnreadCountChange(remaining, hasMore);
      }
      broadcast.post({ type: "marked_read", id: n.id });
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setMarking(null);
    }
  }

  async function markAllRead() {
    if (bulkBusy) return;
    setBulkBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/notifications/mark-all-read", {});
      if (tab === "unread") {
        setItems([]);
      } else {
        const now = new Date().toISOString();
        setItems((prev) =>
          prev.map((x) => (x.read_at ? x : { ...x, read_at: now })),
        );
      }
      onUnreadCountChange?.(0, false);
      broadcast.post({ type: "all_read" });
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setBulkBusy(false);
    }
  }

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        aria-label="關閉通知中心"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/30"
      />

      <aside className="fixed right-0 top-0 z-50 flex h-full w-[420px] flex-col bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-[var(--text-secondary)]" />
            <span className="text-base font-semibold text-[var(--text-primary)]">
              通知中心
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fetchItems(tab)}
              disabled={loading}
              title="重新整理"
              className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[#F1F5F9] disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              type="button"
              onClick={onClose}
              title="關閉"
              className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[#F1F5F9]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
          <div className="flex">
            {TABS.map((t) => (
              <button
                key={t.value}
                onClick={() => setTab(t.value)}
                className={`px-3 py-2 text-[13px] ${
                  tab === t.value
                    ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                    : "font-medium text-[var(--text-secondary)]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={markAllRead}
            disabled={bulkBusy || loading || items.every((x) => !!x.read_at)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-medium text-[var(--primary)] hover:bg-[#EFF6FF] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckCheck className="h-[14px] w-[14px]" />
            {bulkBusy ? "處理中…" : "全部標為已讀"}
          </button>
        </div>

        {error && (
          <div className="mx-5 mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          {loading && items.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              載入中…
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
              {tab === "unread" ? "目前沒有未讀通知" : "目前沒有通知"}
            </div>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {items.map((n) => {
                const meta = SEVERITY_META[n.severity];
                const Icon = meta.Icon;
                const unread = !n.read_at;
                const url = n.related_entity?.url ?? null;
                const typeLabel = TYPE_LABEL[n.type] ?? n.type;
                return (
                  <li
                    key={n.id}
                    className={`flex gap-3 px-5 py-4 ${
                      unread ? "bg-[#F8FAFC]" : "bg-white"
                    }`}
                  >
                    <div
                      className="mt-[2px] flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
                      style={{ backgroundColor: meta.bg }}
                    >
                      <Icon className="h-4 w-4" style={{ color: meta.color }} />
                    </div>
                    <div className="flex flex-1 flex-col gap-1">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                          {n.title}
                        </span>
                        {unread && (
                          <span className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-[var(--primary)]" />
                        )}
                      </div>
                      <span className="text-[12px] leading-[1.5] text-[var(--text-secondary)]">
                        {n.body}
                      </span>
                      <div className="mt-1 flex items-center gap-3 text-[11px] text-[var(--text-disabled)]">
                        <span
                          className="rounded px-[6px] py-[1px]"
                          style={{ backgroundColor: meta.bg, color: meta.color }}
                        >
                          {typeLabel}
                        </span>
                        <span>{formatRelative(n.created_at)}</span>
                      </div>
                      <div className="mt-2 flex items-center gap-3">
                        {unread && (
                          <button
                            type="button"
                            onClick={() => markOneRead(n)}
                            disabled={marking === n.id}
                            className="text-[11px] font-medium text-[var(--primary)] hover:underline disabled:opacity-50"
                          >
                            {marking === n.id ? "標記中…" : "標為已讀"}
                          </button>
                        )}
                        {url && (
                          <Link
                            href={url}
                            onClick={() => {
                              if (unread) markOneRead(n);
                              onClose();
                            }}
                            className="flex items-center gap-1 text-[11px] font-medium text-[var(--primary)] hover:underline"
                          >
                            前往
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {hasMore && items.length > 0 && (
            <div className="px-5 py-3 text-center text-[11px] text-[var(--text-disabled)]">
              僅顯示最近 {PAGE_LIMIT} 筆
            </div>
          )}
        </div>

        <div className="border-t border-[var(--border)] px-5 py-3">
          <Link
            href="/notifications"
            onClick={onClose}
            className="flex items-center justify-center gap-1 rounded-md py-2 text-[13px] font-medium text-[var(--primary)] hover:bg-[#EFF6FF]"
          >
            查看全部通知
            <ExternalLink className="h-[14px] w-[14px]" />
          </Link>
        </div>
      </aside>
    </>
  );
}
