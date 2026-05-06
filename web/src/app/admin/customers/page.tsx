"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Search,
  UserPlus,
  Users,
  ShieldAlert,
  Clock,
  ChevronDown,
  Eye,
  MoreHorizontal,
  X,
  Lock,
  RefreshCw,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type Customer = components["schemas"]["Customer"];
type CustomerPage = components["schemas"]["CustomerPage"];

const PAGE_LIMIT = 20;

function maskLineId(line: string | null | undefined): string {
  if (!line) return "—";
  if (line.length <= 10) return line;
  return `${line.slice(0, 5)}****${line.slice(-4)}`;
}

function avatarChar(c: Customer): string {
  if (c.display_name) return c.display_name[0];
  if (c.phone) return c.phone[0];
  return c.id[0].toUpperCase();
}

function formatDateOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

const columns = [
  { label: "客戶", width: "w-[220px]" },
  { label: "LINE ID", width: "w-[150px]" },
  { label: "地址", width: "w-[260px]" },
  { label: "對話", width: "w-[80px]" },
  { label: "工單", width: "w-[80px]" },
  { label: "最近服務", width: "w-[120px]" },
  { label: "最近互動", width: "w-[120px]" },
  { label: "", width: "w-[60px]" },
];

export default function CustomersPage() {
  const [items, setItems] = useState<Customer[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  async function fetchPage(cursor: string | null) {
    if (cursor === null) setLoading(true);
    else setLoadingMore(true);
    setError(null);
    try {
      const res = await api.get<CustomerPage>("/api/v1/customers", {
        query: {
          limit: PAGE_LIMIT,
          ...(cursor ? { cursor } : {}),
        },
      });
      const fetched = res.items ?? [];
      setItems((prev) => (cursor === null ? fetched : [...prev, ...fetched]));
      setHasMore(!!res.has_more);
      setNextCursor(res.next_cursor ?? null);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.errorCode} (${e.status})：${e.message}`
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    fetchPage(null);
  }, []);

  const filtered = searchQuery
    ? items.filter((c) => {
        const q = searchQuery.toLowerCase();
        return (
          (c.display_name ?? "").toLowerCase().includes(q) ||
          (c.phone ?? "").toLowerCase().includes(q) ||
          (c.line_user_id ?? "").toLowerCase().includes(q) ||
          (c.address ?? "").toLowerCase().includes(q)
        );
      })
    : items;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
                客戶主檔
              </h1>
              <span className="flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-[2px] text-xs text-[var(--primary)]">
                <Lock className="h-3 w-3" />
                SmartLock 租戶
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex w-80 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
                <Search className="h-4 w-4 text-[var(--text-disabled)]" />
                <input
                  type="text"
                  placeholder="本頁過濾：姓名 / 電話 / LINE ID / 地址…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")}>
                    <X className="h-4 w-4 text-[var(--text-disabled)]" />
                  </button>
                )}
              </div>
              <button
                onClick={() => fetchPage(null)}
                disabled={loading}
                title="重新整理"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${
                    loading ? "animate-spin" : ""
                  }`}
                />
              </button>
              <button
                disabled
                title="即將推出"
                className="flex cursor-not-allowed items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 opacity-60"
              >
                <UserPlus className="h-4 w-4 text-white" />
                <span className="text-[13px] font-medium text-white">
                  新增客戶
                </span>
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Summary Stats — mock with banner */}
          <div className="grid grid-cols-4 gap-4">
            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
                <Users className="h-5 w-5 text-[var(--primary)]" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  本頁客戶數
                </span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {items.length}
                  {hasMore && "+"}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
                <Users className="h-5 w-5 text-green-600" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  活躍客戶
                </span>
                <span className="text-xl font-bold text-[var(--text-disabled)]">
                  —
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  待活躍判定規則
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50">
                <ShieldAlert className="h-5 w-5 text-red-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  高風險客戶
                </span>
                <span className="text-xl font-bold text-[var(--text-disabled)]">
                  —
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  待風險引擎
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50">
                <Clock className="h-5 w-5 text-amber-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  保固即將到期
                </span>
                <span className="text-xl font-bold text-[var(--text-disabled)]">
                  —
                </span>
                <span className="text-[11px] text-[var(--text-disabled)]">
                  待保固模組
                </span>
              </div>
            </div>
          </div>

          {/* Filter Bar — disabled */}
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 opacity-60">
            {["風險等級", "設備品牌", "保固狀態", "偏好技師"].map((label) => (
              <button
                key={label}
                disabled
                title="即將推出"
                className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-disabled)]"
              >
                {label}
                <ChevronDown className="h-3 w-3 text-[var(--text-disabled)]" />
              </button>
            ))}
          </div>

          {/* Data Table */}
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
              {columns.map((col) => (
                <div key={col.label || "actions"} className={col.width}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {loading && items.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                載入中…
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-[13px] text-[var(--text-secondary)]">
                {searchQuery ? "本頁無符合的客戶" : "目前沒有客戶資料"}
              </div>
            ) : (
              filtered.map((c) => (
                <Link
                  key={c.id}
                  href={`/admin/customers/${c.id}`}
                  className="group flex items-center border-t border-[var(--border)] px-4 py-3 transition-colors hover:bg-blue-50"
                >
                  <div className="flex w-[220px] items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-xs font-semibold text-[var(--primary)]">
                      {avatarChar(c)}
                    </div>
                    <div className="flex flex-col">
                      <span
                        className="truncate text-[13px] font-medium text-[var(--text-primary)]"
                        title={c.display_name}
                      >
                        {c.display_name}
                      </span>
                      <span className="text-[11px] text-[var(--text-secondary)]">
                        {c.phone ?? "—"}
                      </span>
                    </div>
                  </div>

                  <div className="w-[150px]">
                    <span
                      className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-secondary)]"
                      title={c.line_user_id ?? undefined}
                    >
                      {maskLineId(c.line_user_id)}
                    </span>
                  </div>

                  <div className="w-[260px]">
                    <span
                      className="block truncate text-[13px] text-[var(--text-primary)]"
                      title={c.address ?? ""}
                    >
                      {c.address ?? "—"}
                    </span>
                  </div>

                  <div className="w-[80px]">
                    <span className="text-[13px] text-[var(--text-primary)]">
                      {c.total_conversations}
                    </span>
                  </div>

                  <div className="w-[80px]">
                    <span className="text-[13px] text-[var(--text-primary)]">
                      {c.total_orders}
                    </span>
                  </div>

                  <div className="w-[120px]">
                    <span className="text-[13px] text-[var(--text-secondary)]">
                      {formatDateOnly(c.last_service_at)}
                    </span>
                  </div>

                  <div className="w-[120px]">
                    <span
                      className="text-[13px] text-[var(--text-secondary)]"
                      title={c.last_active_at ?? ""}
                    >
                      {c.last_active_at ? formatRelative(c.last_active_at) : "—"}
                    </span>
                  </div>

                  <div className="flex w-[60px] items-center gap-1">
                    <button
                      disabled
                      title="即將推出（客戶詳情頁）"
                      className="cursor-not-allowed rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-60"
                    >
                      <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
                    </button>
                    <button
                      disabled
                      title="即將推出"
                      className="cursor-not-allowed rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-60"
                    >
                      <MoreHorizontal className="h-4 w-4 text-[var(--text-secondary)]" />
                    </button>
                  </div>
                </Link>
              ))
            )}

            {hasMore && filtered.length > 0 && (
              <div className="flex items-center justify-center border-t border-[var(--border)] px-4 py-3">
                <button
                  onClick={() => nextCursor && fetchPage(nextCursor)}
                  disabled={loadingMore}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loadingMore ? "載入中…" : "載入更多"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
