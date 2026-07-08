"use client";

/**
 * FR-0051 SOP Feedback — sentiment + score 統計 + filter。
 *
 * 對應 backend: GET /tenants/{tid}/sop-feedback
 */

import { useEffect, useState } from "react";
import { RefreshCw, ThumbsUp, ThumbsDown, Minus } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import {
  type SopFeedbackItem,
  type SopSentiment,
  SOP_FEEDBACK_SOURCE_LABEL,
  SOP_SENTIMENT_LABEL,
  SOP_SENTIMENT_COLOR,
  SOP_TYPE_LABEL,
  formatDateTime,
  type BadgeColor,
} from "@shared/components/phase-ii";

const SENTIMENT_TABS: { value: SopSentiment | "all"; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "positive", label: "正向" },
  { value: "neutral", label: "中性" },
  { value: "negative", label: "負向" },
];

const COLOR_BG: Record<BadgeColor, { bg: string; text: string }> = {
  red: { bg: "#fef0ef", text: "#d70015" },
  orange: { bg: "#fff4e5", text: "#c5510b" },
  yellow: { bg: "#fef9c3", text: "#854d0e" },
  green: { bg: "#e8f5e9", text: "#15803d" },
  blue: { bg: "#dbeafe", text: "#1e3a8a" },
  purple: { bg: "#ede9fe", text: "#5b21b6" },
  gray: { bg: "#f4f4f5", text: "#52525b" },
};

function formatError(e: unknown): string {
  return friendlyError(e);
}

export default function SopFeedbackPage() {
  const [items, setItems] = useState<SopFeedbackItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentiment, setSentiment] = useState<SopSentiment | "all">("all");

  async function fetch() {
    setLoading(true);
    setError(null);
    try {
      const q = sentiment === "all" ? "" : `?sentiment=${sentiment}&limit=100`;
      const path = tenantPath(
        sentiment === "all" ? "/sop-feedback?limit=100" : `/sop-feedback${q}`,
      );
      const res = await api.get<SopFeedbackItem[] | { items: SopFeedbackItem[] }>(path);
      setItems(Array.isArray(res) ? res : res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sentiment]);

  function renderSentiment(s: SopSentiment) {
    const c = SOP_SENTIMENT_COLOR[s];
    const sty = COLOR_BG[c];
    const Icon =
      s === "positive" ? ThumbsUp : s === "negative" ? ThumbsDown : Minus;
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        <Icon size={12} />
        {SOP_SENTIMENT_LABEL[s]}
      </span>
    );
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">SOP 反饋螺旋</h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0051 — 客戶評分 / 技師現場 / RMA / AI / CSM 5 來源 + sentiment
            </p>
          </div>
          <button
            type="button"
            onClick={fetch}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            重新整理
          </button>
        </header>

        <div className="mb-4 flex flex-wrap gap-2">
          {SENTIMENT_TABS.map((tab) => {
            const active = sentiment === tab.value;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setSentiment(tab.value)}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">時間</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">SOP ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">類型</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">來源</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">情緒</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">分數</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">意見</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-gray-500">無反饋</td>
                </tr>
              )}
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatDateTime(it.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-mono text-xs text-gray-700">
                    {it.sop_id.slice(0, 12)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    {SOP_TYPE_LABEL[it.sop_type]}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    {SOP_FEEDBACK_SOURCE_LABEL[it.source]}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderSentiment(it.sentiment)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-medium">
                    {it.score !== null ? (
                      <span
                        className={
                          it.score > 0
                            ? "text-green-600"
                            : it.score < 0
                              ? "text-red-600"
                              : "text-gray-500"
                        }
                      >
                        {it.score > 0 ? `+${it.score}` : it.score}
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 max-w-xs truncate" title={it.comment ?? ""}>
                    {it.comment ?? <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
