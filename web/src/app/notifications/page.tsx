"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Bell,
  CheckCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  ExternalLink,
  RefreshCw,
  Settings,
  Archive,
  X,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import RealtimeIndicator from "@/components/realtime/RealtimeIndicator";
import { ApiError, api, getCurrentSession } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useRealtimeChannel } from "@/lib/useRealtimeChannel";
import {
  BROADCAST_CHANNELS,
  NotificationBroadcastEvent,
  useBroadcast,
} from "@/lib/useBroadcast";
import { useTranslations } from "@/components/i18n/LocaleProvider";
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

type StatusFilter = "all" | "unread" | "read" | "archived";

const PAGE_LIMIT = 50;

const STATUS_TAB_VALUES: StatusFilter[] = ["unread", "all", "read", "archived"];

const TYPE_FILTER_VALUES: (NotificationType | "all")[] = [
  "all",
  "work_order",
  "refund",
  "dispute",
  "rbac",
  "inventory",
  "sla",
  "system",
  "mention",
];

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

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function NotificationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("pages.notifications");
  const tTabs = useTranslations("pages.notifications.tabs");
  const tTypes = useTranslations("pages.notifications.types");
  const tSev = useTranslations("pages.notifications.severity");

  const initialTab = (searchParams.get("tab") as StatusFilter) || "unread";
  const initialType =
    (searchParams.get("type") as NotificationType | "all") || "all";
  const deepLinkId = searchParams.get("id");

  const [tab, setTab] = useState<StatusFilter>(
    STATUS_TAB_VALUES.includes(initialTab) ? initialTab : "unread",
  );
  const [typeFilter, setTypeFilter] = useState<NotificationType | "all">(
    TYPE_FILTER_VALUES.includes(initialType) ? initialType : "all",
  );

  const [items, setItems] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(deepLinkId);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [marking, setMarking] = useState<string | null>(null);

  // Sync URL query when tab / type filter / selected id changes
  useEffect(() => {
    const params = new URLSearchParams();
    if (tab !== "unread") params.set("tab", tab);
    if (typeFilter !== "all") params.set("type", typeFilter);
    if (selectedId) params.set("id", selectedId);
    const qs = params.toString();
    router.replace(qs ? `/notifications?${qs}` : "/notifications", {
      scroll: false,
    });
  }, [tab, typeFilter, selectedId, router]);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: PAGE_LIMIT };
      if (tab !== "all") query.status = tab;
      if (typeFilter !== "all") query.type = typeFilter;
      const res = await api.get<NotificationListResponse>(
        "/api/v1/notifications",
        { query },
      );
      const next = res.items ?? [];
      setItems(next);
      setHasMore(!!res.has_more);
      const fromCount =
        typeof res.unread_count === "number"
          ? res.unread_count
          : next.filter((n) => !n.read_at).length;
      setUnreadCount(fromCount);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [tab, typeFilter]);

  useEffect(() => {
    fetchItems();
    setSelectedIds(new Set());
  }, [fetchItems]);

  // 跨 tab 同步：同 user 開多 tab 時，標記已讀/全部已讀/封存等動作互相同步
  const broadcast = useBroadcast<NotificationBroadcastEvent>(
    BROADCAST_CHANNELS.notifications,
    (event) => {
      if (event.type === "marked_read") {
        const now = new Date().toISOString();
        setItems((prev) =>
          prev.map((x) =>
            x.id === event.id && !x.read_at ? { ...x, read_at: now } : x,
          ),
        );
        setUnreadCount((c) => Math.max(0, c - 1));
        if (tab === "unread") {
          setItems((prev) => prev.filter((x) => x.id !== event.id));
        }
      } else if (event.type === "archived") {
        setItems((prev) => prev.filter((x) => x.id !== event.id));
      } else if (event.type === "all_read") {
        const now = new Date().toISOString();
        setItems((prev) =>
          prev.map((x) => (x.read_at ? x : { ...x, read_at: now })),
        );
        setUnreadCount(0);
        if (tab === "unread") setItems([]);
      } else if (event.type === "new_received") {
        // 其他 tab 透過 WS 收到新通知，本 tab 重抓以拿到完整資料
        fetchItems();
      }
    },
  );

  // 即時推送：新通知插入列表頂端、增加未讀計數
  const userId = useMemo(() => getCurrentSession()?.userId ?? null, []);
  const { status: rtStatus } = useRealtimeChannel<Notification>({
    channelPath: userId ? `/realtime/notifications/${userId}` : "",
    enabled: !!userId,
    onMessage: (msg) => {
      const incoming = (msg.payload ?? msg) as Notification | undefined;
      if (!incoming?.id) return;
      // 依 tab/type 過濾，不符合直接忽略
      if (typeFilter !== "all" && incoming.type !== typeFilter) return;
      const isUnread = !incoming.read_at;
      if (tab === "unread" && !isUnread) return;
      if (tab === "read" && isUnread) return;
      setItems((prev) => {
        if (prev.some((x) => x.id === incoming.id)) return prev;
        return [incoming, ...prev];
      });
      if (isUnread) setUnreadCount((c) => c + 1);
      broadcast.post({ type: "new_received", id: incoming.id });
    },
  });

  const selectedItem = useMemo(
    () => items.find((n) => n.id === selectedId) ?? null,
    [items, selectedId],
  );

  async function markOneRead(n: Notification) {
    if (n.read_at || marking) return;
    setMarking(n.id);
    try {
      await api.patch(`/api/v1/notifications/${encodeURIComponent(n.id)}`, {
        read_at: new Date().toISOString(),
      });
      const now = new Date().toISOString();
      setItems((prev) =>
        prev.map((x) => (x.id === n.id ? { ...x, read_at: now } : x)),
      );
      setUnreadCount((c) => Math.max(0, c - 1));
      broadcast.post({ type: "marked_read", id: n.id });
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setMarking(null);
    }
  }

  async function archiveOne(n: Notification) {
    setMarking(n.id);
    try {
      await api.patch(`/api/v1/notifications/${encodeURIComponent(n.id)}`, {
        archived_at: new Date().toISOString(),
      });
      setItems((prev) => prev.filter((x) => x.id !== n.id));
      if (selectedId === n.id) setSelectedId(null);
      broadcast.post({ type: "archived", id: n.id });
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setMarking(null);
    }
  }

  async function markAllRead() {
    if (bulkBusy) return;
    setBulkBusy(true);
    try {
      await api.post(
        "/api/v1/notifications/mark-all-read",
        typeFilter === "all" ? {} : { filter: { type: [typeFilter] } },
      );
      const now = new Date().toISOString();
      setItems((prev) =>
        prev.map((x) => (x.read_at ? x : { ...x, read_at: now })),
      );
      setUnreadCount(0);
      if (tab === "unread") setItems([]);
      broadcast.post({ type: "all_read" });
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setBulkBusy(false);
    }
  }

  async function bulkAction(action: "mark_read" | "archive") {
    if (bulkBusy || selectedIds.size === 0) return;
    setBulkBusy(true);
    try {
      await api.post("/api/v1/notifications/bulk", {
        ids: Array.from(selectedIds),
        action,
      });
      if (action === "archive") {
        setItems((prev) => prev.filter((x) => !selectedIds.has(x.id)));
      } else if (action === "mark_read") {
        const now = new Date().toISOString();
        setItems((prev) =>
          prev.map((x) =>
            selectedIds.has(x.id) && !x.read_at ? { ...x, read_at: now } : x,
          ),
        );
        setUnreadCount((c) => Math.max(0, c - selectedIds.size));
        if (tab === "unread") {
          setItems((prev) => prev.filter((x) => !selectedIds.has(x.id)));
        }
      }
      setSelectedIds(new Set());
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setBulkBusy(false);
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(items.map((n) => n.id)));
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* header_bar */}
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Bell className="h-6 w-6 text-[var(--text-secondary)]" />
              <h1 className="text-[24px] font-semibold text-[#18181B]">
                {t("title")}
              </h1>
              {unreadCount > 0 && (
                <span className="rounded-full bg-[var(--primary)] px-3 py-[2px] text-[12px] font-semibold text-white">
                  {t("unreadBadge", { count: String(unreadCount) })}
                </span>
              )}
              <RealtimeIndicator status={rtStatus} />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={fetchItems}
                disabled={loading}
                title={t("refresh")}
                className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] bg-white text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                />
              </button>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={markAllRead}
                  disabled={bulkBusy}
                  className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-medium text-[var(--primary)] hover:bg-[#EFF6FF] disabled:opacity-50"
                >
                  <CheckCheck className="h-4 w-4" />
                  {bulkBusy ? t("markAllBusy") : t("markAll")}
                </button>
              )}
              <Link
                href="/settings?tab=notifications"
                title={t("preferences")}
                className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] bg-white text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                <Settings className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {/* tab_group */}
          <div className="flex">
            {STATUS_TAB_VALUES.map((value) => (
              <button
                key={value}
                onClick={() => setTab(value)}
                className={`px-4 py-[10px] text-[14px] ${
                  tab === value
                    ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                    : "font-medium text-[#71717A] hover:text-[var(--text-primary)]"
                }`}
              >
                {tTabs(value)}
              </button>
            ))}
          </div>

          {/* filter_chips */}
          <div className="flex flex-wrap items-center gap-2">
            {TYPE_FILTER_VALUES.map((value) => (
              <button
                key={value}
                onClick={() => setTypeFilter(value)}
                className={`rounded-full border px-3 py-1 text-[12px] font-medium transition ${
                  typeFilter === value
                    ? "border-[var(--primary)] bg-[#EFF6FF] text-[var(--primary)]"
                    : "border-[var(--border)] bg-white text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                }`}
              >
                {tTypes(value)}
              </button>
            ))}
          </div>
        </div>

        {/* main 區：左 list + 右 preview */}
        <div className="flex flex-1 overflow-hidden">
          {/* notification_list */}
          <div className="flex flex-1 flex-col overflow-hidden">
            {error && (
              <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                {error}
              </div>
            )}

            {/* 列表頂部小工具 */}
            <div className="flex items-center justify-between border-b border-[var(--border)] bg-white px-6 py-2 text-[12px] text-[var(--text-secondary)]">
              <span>
                {loading
                  ? t("loading")
                  : t("totalCount", {
                      count: String(items.length),
                      plus: hasMore ? "+" : "",
                    })}
              </span>
              {items.length > 0 && (
                <button
                  type="button"
                  onClick={
                    selectedIds.size === items.length
                      ? () => setSelectedIds(new Set())
                      : selectAll
                  }
                  className="text-[12px] font-medium text-[var(--primary)] hover:underline"
                >
                  {selectedIds.size === items.length ? t("clearSelection") : t("selectAll")}
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto">
              {loading && items.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                  {t("loading")}
                </div>
              ) : items.length === 0 ? (
                <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
                  <Bell className="h-10 w-10 text-[var(--text-disabled)]" />
                  <p className="text-[14px]">
                    {tab === "unread"
                      ? t("empty.unread")
                      : tab === "archived"
                        ? t("empty.archived")
                        : t("empty.all")}
                  </p>
                  <Link
                    href="/settings?tab=notifications"
                    className="text-[12px] text-[var(--primary)] hover:underline"
                  >
                    {t("managePrefs")}
                  </Link>
                </div>
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {items.map((n) => {
                    const meta = SEVERITY_META[n.severity];
                    const Icon = meta.Icon;
                    const unread = !n.read_at;
                    const checked = selectedIds.has(n.id);
                    const active = selectedId === n.id;
                    const typeLabel = tTypes(n.type);
                    return (
                      <li
                        key={n.id}
                        onClick={() => {
                          setSelectedId(n.id);
                          if (unread) markOneRead(n);
                        }}
                        className={`flex cursor-pointer gap-3 px-6 py-4 transition ${
                          active
                            ? "bg-[#EFF6FF]"
                            : unread
                              ? "bg-[#F0F9FF]"
                              : "bg-white hover:bg-[var(--bg-page)]"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => toggleSelect(n.id)}
                          className="mt-2 h-4 w-4 cursor-pointer accent-[var(--primary)]"
                        />
                        <div
                          className="mt-[2px] flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full"
                          style={{ backgroundColor: meta.bg }}
                        >
                          <Icon
                            className="h-[18px] w-[18px]"
                            style={{ color: meta.color }}
                          />
                        </div>
                        <div className="flex flex-1 flex-col gap-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-[14px] font-semibold text-[var(--text-primary)] line-clamp-2">
                              {n.title}
                            </span>
                            {unread && (
                              <span className="mt-[6px] h-2 w-2 flex-shrink-0 rounded-full bg-[var(--primary)]" />
                            )}
                          </div>
                          <span className="text-[12px] leading-[1.5] text-[var(--text-secondary)] line-clamp-1">
                            {n.body}
                          </span>
                          <div className="mt-1 flex items-center gap-3 text-[11px] text-[var(--text-disabled)]">
                            <span
                              className="rounded px-[6px] py-[1px] font-medium"
                              style={{
                                backgroundColor: meta.bg,
                                color: meta.color,
                              }}
                            >
                              {typeLabel}
                            </span>
                            {n.severity !== "info" && (
                              <span
                                className="rounded px-[6px] py-[1px] font-medium"
                                style={{
                                  backgroundColor:
                                    n.severity === "critical"
                                      ? "#FEE2E2"
                                      : "#FEF3C7",
                                  color:
                                    n.severity === "critical"
                                      ? "#DC2626"
                                      : "#D97706",
                                }}
                              >
                                {n.severity === "critical" ? tSev("critical") : tSev("warning")}
                              </span>
                            )}
                            <span>{formatRelative(n.created_at)}</span>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
              {hasMore && items.length > 0 && (
                <div className="px-6 py-3 text-center text-[11px] text-[var(--text-disabled)]">
                  {t("moreHint", { limit: String(PAGE_LIMIT) })}
                </div>
              )}
            </div>
          </div>

          {/* detail_preview */}
          {selectedItem && (
            <aside className="hidden w-[400px] flex-col border-l border-[var(--border)] bg-white md:flex">
              <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
                <span className="text-[14px] font-semibold text-[var(--text-primary)]">
                  {t("detail")}
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <div className="mb-3 flex items-center gap-2 text-[11px]">
                  <span
                    className="rounded px-[6px] py-[1px] font-medium"
                    style={{
                      backgroundColor: SEVERITY_META[selectedItem.severity].bg,
                      color: SEVERITY_META[selectedItem.severity].color,
                    }}
                  >
                    {tTypes(selectedItem.type)}
                  </span>
                  <span className="text-[var(--text-disabled)]">
                    {formatRelative(selectedItem.created_at)}
                  </span>
                  <span className="text-[var(--text-disabled)]">·</span>
                  <span className="text-[var(--text-disabled)]">
                    {t("fromSource", { source: selectedItem.source })}
                  </span>
                </div>
                <h2 className="mb-2 text-[16px] font-semibold text-[var(--text-primary)]">
                  {selectedItem.title}
                </h2>
                <p className="whitespace-pre-line text-[13px] leading-[1.6] text-[var(--text-secondary)]">
                  {selectedItem.body}
                </p>

                {selectedItem.related_entity?.url && (
                  <Link
                    href={selectedItem.related_entity.url}
                    className="mt-4 inline-flex items-center gap-1 rounded-md bg-[var(--primary)] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#1D4ED8]"
                  >
                    {t("openLink")}
                    {selectedItem.related_entity.type
                      ? ` ${selectedItem.related_entity.type}`
                      : ` ${t("openLinkSource")}`}
                    <ExternalLink className="h-[14px] w-[14px]" />
                  </Link>
                )}

                {selectedItem.actions && selectedItem.actions.length > 0 && (
                  <div className="mt-4 flex flex-col gap-2">
                    <span className="text-[12px] font-medium text-[var(--text-secondary)]">
                      {t("quickActions")}
                    </span>
                    {selectedItem.actions.map((a, i) =>
                      a.endpoint && a.label ? (
                        <Link
                          key={i}
                          href={a.endpoint}
                          className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)]"
                        >
                          {a.label}
                        </Link>
                      ) : null,
                    )}
                  </div>
                )}
              </div>

              <div className="flex gap-2 border-t border-[var(--border)] px-5 py-3">
                {!selectedItem.read_at && (
                  <button
                    type="button"
                    onClick={() => markOneRead(selectedItem)}
                    disabled={marking === selectedItem.id}
                    className="flex flex-1 items-center justify-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
                  >
                    <CheckCheck className="h-4 w-4" />
                    {t("markRead")}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => archiveOne(selectedItem)}
                  disabled={marking === selectedItem.id}
                  className="flex flex-1 items-center justify-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
                >
                  <Archive className="h-4 w-4" />
                  {t("archive")}
                </button>
              </div>
            </aside>
          )}
        </div>

        {/* bulk_actions_toolbar */}
        {selectedIds.size > 0 && (
          <div className="sticky bottom-0 flex items-center justify-between gap-3 border-t border-[var(--border)] bg-white px-6 py-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              {t("selectedCount", { count: String(selectedIds.size) })}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => bulkAction("mark_read")}
                disabled={bulkBusy}
                className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-[6px] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                <CheckCheck className="h-4 w-4" />
                {t("bulkMarkRead")}
              </button>
              <button
                type="button"
                onClick={() => bulkAction("archive")}
                disabled={bulkBusy}
                className="flex items-center gap-1 rounded-md border border-[var(--border)] bg-white px-3 py-[6px] text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                <Archive className="h-4 w-4" />
                {t("bulkArchive")}
              </button>
              <button
                type="button"
                onClick={() => setSelectedIds(new Set())}
                className="rounded-md px-3 py-[6px] text-[13px] font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
              >
                {t("bulkCancel")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
