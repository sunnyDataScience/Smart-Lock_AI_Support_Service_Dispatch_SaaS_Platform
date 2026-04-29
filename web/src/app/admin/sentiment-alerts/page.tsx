"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type SentimentAlert = components["schemas"]["SentimentAlert"];
type SentimentAlertPage = components["schemas"]["SentimentAlertPage"];
type SentimentAlertStatus = components["schemas"]["SentimentAlertStatus"];
type SentimentLabel = SentimentAlert["sentiment_label"];

const STATUS_LABEL: Record<SentimentAlertStatus, string> = {
  pending: "未處理",
  acknowledged: "已確認",
  resolved: "已結案",
};

const STATUS_BADGE: Record<SentimentAlertStatus, { bg: string; text: string }> = {
  pending: { bg: "#FEE2E2", text: "#B91C1C" },
  acknowledged: { bg: "#FEF3C7", text: "#92400E" },
  resolved: { bg: "#DCFCE7", text: "#166534" },
};

const STATUS_OPTIONS: SentimentAlertStatus[] = ["pending", "acknowledged", "resolved"];

const LABEL_TEXT: Record<SentimentLabel, string> = {
  very_negative: "極度負面",
  negative: "負面",
  neutral: "中性",
  positive: "正面",
};

const LABEL_BADGE: Record<SentimentLabel, { bg: string; text: string }> = {
  very_negative: { bg: "#7F1D1D", text: "#FECACA" },
  negative: { bg: "#FEE2E2", text: "#B91C1C" },
  neutral: { bg: "#E5E7EB", text: "#374151" },
  positive: { bg: "#DCFCE7", text: "#166534" },
};

const PAGE_SIZE = 20;

const columns = [
  { label: "時間", width: "w-[140px]" },
  { label: "狀態", width: "w-[100px]" },
  { label: "情緒", width: "w-[100px]" },
  { label: "信心", width: "w-[80px]" },
  { label: "客戶訊息片段", width: "flex-1" },
  { label: "關鍵字", width: "w-[200px]" },
  { label: "對話", width: "w-[100px]" },
];

function formatConfidence(c: number): string {
  return `${Math.round(c * 100)}%`;
}

export default function SentimentAlertsPage() {
  const [items, setItems] = useState<SentimentAlert[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<SentimentAlertStatus | "">("");

  const fetchPage = useCallback(
    async (afterCursor: string | null, append: boolean, filter: SentimentAlertStatus | "") => {
      setLoading(true);
      setError(null);
      try {
        const query: Record<string, string | number> = { limit: PAGE_SIZE };
        if (afterCursor) query.cursor = afterCursor;
        if (filter) query.status = filter;
        const res = await api.get<SentimentAlertPage>("/api/v1/sentiment/alerts", { query });
        const newItems = res.items ?? [];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        setCursor(res.next_cursor ?? null);
        setHasMore(!!res.has_more);
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
      }
    },
    [],
  );

  useEffect(() => {
    fetchPage(null, false, statusFilter);
  }, [fetchPage, statusFilter]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-[#DC2626]" />
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                負面情緒告警
              </h1>
            </div>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            目前僅支援列表瀏覽。「處理 / 結案」按鈕（updateSentimentAlert）將於下一個 phase 接入。
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-[var(--text-secondary)]">狀態</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as SentimentAlertStatus | "")}
                className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]"
              >
                <option value="">全部</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>

            {statusFilter && (
              <button
                onClick={() => setStatusFilter("")}
                className="rounded-md px-3 py-2"
              >
                <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                  清除篩選
                </span>
              </button>
            )}

            <span className="ml-auto text-[13px] text-[var(--text-secondary)]">
              {loading ? "載入中…" : `共 ${items.length} 筆${hasMore ? "+" : ""}`}
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center bg-[#F8FAFC] px-4" style={{ height: 44 }}>
              {columns.map((col, i) => (
                <div key={i} className={`flex h-full items-center ${col.width}`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {items.length === 0 && !loading && (
              <div className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
                沒有符合條件的告警紀錄
              </div>
            )}

            {items.map((row) => {
              const status = row.status as SentimentAlertStatus;
              const label = row.sentiment_label as SentimentLabel;
              const sBadge = STATUS_BADGE[status];
              const lBadge = LABEL_BADGE[label];
              const keywords = row.detected_keywords ?? [];
              const message = row.consumer_message ?? "";
              return (
                <div
                  key={row.id}
                  className="flex items-center border-t border-t-[var(--border)] px-4"
                  style={{ minHeight: 56 }}
                >
                  <div className="flex h-full w-[140px] items-center">
                    <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-primary)]">
                      {formatRelative(row.created_at)}
                    </span>
                  </div>

                  <div className="flex h-full w-[100px] items-center">
                    <span
                      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                      style={{ backgroundColor: sBadge.bg, color: sBadge.text }}
                    >
                      {STATUS_LABEL[status]}
                    </span>
                  </div>

                  <div className="flex h-full w-[100px] items-center">
                    <span
                      className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                      style={{ backgroundColor: lBadge.bg, color: lBadge.text }}
                    >
                      {LABEL_TEXT[label]}
                    </span>
                  </div>

                  <div className="flex h-full w-[80px] items-center">
                    <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-primary)]">
                      {formatConfidence(row.confidence)}
                    </span>
                  </div>

                  <div className="flex h-full flex-1 items-center pr-3">
                    <span
                      className="line-clamp-2 text-[13px] text-[var(--text-primary)]"
                      title={message}
                    >
                      {message || "—"}
                    </span>
                  </div>

                  <div className="flex h-full w-[200px] flex-wrap items-center gap-1 py-2">
                    {keywords.length === 0 ? (
                      <span className="text-xs text-[var(--text-disabled)]">—</span>
                    ) : (
                      keywords.slice(0, 4).map((kw, i) => (
                        <span
                          key={i}
                          className="rounded bg-[#F1F5F9] px-[6px] py-[1px] text-[11px] text-[var(--text-secondary)]"
                        >
                          {kw}
                        </span>
                      ))
                    )}
                  </div>

                  <div className="flex h-full w-[100px] items-center">
                    <Link
                      href={`/conversations/${row.conversation_id}`}
                      className="font-['IBM_Plex_Mono'] text-xs text-[var(--primary)] hover:underline"
                    >
                      {row.conversation_id.slice(0, 8)}
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>

          {hasMore && (
            <div className="flex justify-center pt-2">
              <button
                disabled={loading}
                onClick={() => fetchPage(cursor, true, statusFilter)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
              >
                {loading ? "載入中…" : "載入更多"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
