"use client";

/**
 * FR-0046 Dispatcher Commission Statement — 派工員獎金對帳單。
 *
 * 對應 backend: GET /tenants/{tid}/me/commission-statements
 * 對應 Sprint 3 (docs/_ops/phase-ii-web-integration-plan.md §4)
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import {
  type DispatcherCommissionStatement,
  STATEMENT_STATUS_LABEL,
  STATEMENT_STATUS_COLOR,
  formatDecimal,
  daysUntilDeadline,
  type BadgeColor,
} from "@/components/phase-ii";

const STATUS_BG: Record<BadgeColor, { bg: string; text: string }> = {
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

export default function MyCommissionStatementsPage() {
  const [items, setItems] = useState<DispatcherCommissionStatement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchStatements() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<
        DispatcherCommissionStatement[] | { items: DispatcherCommissionStatement[] }
      >(tenantPath("/me/commission-statements"));
      const list = Array.isArray(res) ? res : res.items ?? [];
      setItems(list);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatements();
  }, []);

  function renderBadge(status: DispatcherCommissionStatement["status"]) {
    const color = STATEMENT_STATUS_COLOR[status];
    const sty = STATUS_BG[color];
    return (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {STATEMENT_STATUS_LABEL[status]}
      </span>
    );
  }

  function renderDeadline(s: DispatcherCommissionStatement) {
    if (s.status !== "pending_review" && s.status !== "disputed")
      return <span className="text-gray-400">—</span>;
    const days = daysUntilDeadline(s.dispute_window_ends_at);
    if (days === null) return <span className="text-gray-400">—</span>;
    if (days < 0) return <span className="text-gray-500 italic">已過期</span>;
    if (days < 3) return <span className="text-red-600 font-semibold">{days} 天</span>;
    if (days < 7) return <span className="text-orange-600 font-semibold">{days} 天</span>;
    return <span className="text-gray-700">{days} 天</span>;
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">我的派工獎金對帳單</h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0046 — base + performance bonus − penalty 三段計算
            </p>
          </div>
          <button
            type="button"
            onClick={fetchStatements}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-gray-300 bg-[var(--bg-surface)] px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            重新整理
          </button>
        </header>

        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-gray-200 bg-[var(--bg-surface)]">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">月份</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">狀態</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">派單 / 完工</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">完工率</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">底薪</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">獎金</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">扣款</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">淨額</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">申訴期限</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-[var(--bg-surface)]">
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-sm text-gray-500">無對帳單</td>
                </tr>
              )}
              {items.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    {s.period_year}/{String(s.period_month).padStart(2, "0")}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderBadge(s.status)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {s.total_dispatched_orders} / {s.total_completed_orders}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {s.completion_rate_pct}%
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {formatDecimal(s.base_commission)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-green-600">
                    +{formatDecimal(s.performance_bonus)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-red-600">
                    −{formatDecimal(s.penalty)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-semibold text-gray-900">
                    {formatDecimal(s.net_commission)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderDeadline(s)}</td>
                </tr>
              ))}
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-sm text-gray-500">載入中…</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
