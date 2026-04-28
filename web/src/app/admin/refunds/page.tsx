"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import RefundReviewTable from "@/components/admin/RefundReviewTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type RefundRequest = components["schemas"]["RefundRequest"];
type RefundRequestPage = components["schemas"]["RefundRequestPage"];

const SLA_TIER_2H_MS = 2 * 60 * 60 * 1000;
const SLA_TIER_8H_MS = 8 * 60 * 60 * 1000;

function isOpenForReview(status: RefundRequest["status"]): boolean {
  return status === "pending" || status === "escalated";
}

export default function RefundReviewPage() {
  const [items, setItems] = useState<RefundRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchRefunds = async (opts?: { append?: boolean; cursor?: string | null }) => {
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = { limit: 50 };
      if (opts?.cursor) query.cursor = opts.cursor;
      const res = await api.get<RefundRequestPage>("/api/v1/refunds", { query });
      const newItems = res.items ?? [];
      setItems((prev) => (opts?.append ? [...prev, ...newItems] : newItems));
      setNextCursor(res.next_cursor ?? null);
      setHasMore(res.has_more ?? false);
      setUpdatedAt(new Date());
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
  };

  useEffect(() => {
    fetchRefunds();
  }, []);

  const slaCounts = useMemo(() => {
    const now = Date.now();
    let tier2 = 0;
    let tier8 = 0;
    let tierLong = 0;
    for (const r of items) {
      if (!isOpenForReview(r.status)) continue;
      const ageMs = now - new Date(r.created_at).getTime();
      if (ageMs <= SLA_TIER_2H_MS) tier2 += 1;
      else if (ageMs <= SLA_TIER_8H_MS) tier8 += 1;
      else tierLong += 1;
    }
    return { tier2, tier8, tierLong };
  }, [items]);

  const slaCards = [
    {
      label: "申請 ≤ 2 小時",
      count: slaCounts.tier2,
      labelColor: "#991B1B",
      countColor: "#DC2626",
      bgColor: "#FEE2E2",
    },
    {
      label: "申請 ≤ 8 小時",
      count: slaCounts.tier8,
      labelColor: "#92400E",
      countColor: "#D97706",
      bgColor: "#FEF3C7",
    },
    {
      label: "申請 > 8 小時",
      count: slaCounts.tierLong,
      labelColor: "#065F46",
      countColor: "#059669",
      bgColor: "#D1FAE5",
    },
  ];

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              退款審核佇列
            </h1>
            <button
              onClick={() => fetchRefunds()}
              disabled={loading}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
              title="重新整理"
            >
              <RefreshCw
                className={`h-[14px] w-[14px] text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
              />
            </button>
            <span
              className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
              style={{
                backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                color: error ? "#B91C1C" : "#15803D",
              }}
            >
              <span
                className="h-[6px] w-[6px] rounded-full"
                style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
              />
              {error ? "連線失敗" : "已連線"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {updatedAt
                ? `最後更新：${updatedAt.toLocaleTimeString("zh-TW", { hour12: false })}`
                : "—"}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">·</span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              共 {items.length}{hasMore ? "+" : ""} 筆
            </span>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
            列表為 listRefundRequests 即時資料；SLA 分群以「申請建立至今經過時間」估算（2h / 8h / &gt;8h）。
            核准 / 拒絕、雙簽動作待 submitRefundDecision 寫入路徑與 Idempotency 流程上線後接入。
          </div>

          <div className="flex gap-3">
            {slaCards.map((card) => (
              <div
                key={card.label}
                className="flex flex-1 flex-col gap-1 rounded-lg px-4 py-3"
                style={{ backgroundColor: card.bgColor }}
              >
                <span
                  className="text-[13px] font-medium"
                  style={{ color: card.labelColor }}
                >
                  {card.label}
                </span>
                <span
                  className="text-[28px] font-bold"
                  style={{ color: card.countColor }}
                >
                  {card.count}
                </span>
              </div>
            ))}
          </div>

          <RefundReviewTable items={items} loading={loading} />

          {hasMore && (
            <div className="flex justify-center">
              <button
                onClick={() => fetchRefunds({ append: true, cursor: nextCursor })}
                disabled={loading}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
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
