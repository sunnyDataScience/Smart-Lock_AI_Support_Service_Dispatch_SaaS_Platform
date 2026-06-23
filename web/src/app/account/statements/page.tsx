"use client";

/**
 * FR-0045 Technician AP Statement — 技師薪資對帳單 (含申訴流程)。
 *
 * 對應 backend: GET /tenants/{tid}/tech-statements?technician_id={technicians.id}
 * 對應 Sprint 3 (docs/_ops/phase-ii-web-integration-plan.md §4)
 */

import { useEffect, useState } from "react";
import { RefreshCw, AlertTriangle } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import {
  type TechStatement,
  STATEMENT_STATUS_LABEL,
  STATEMENT_STATUS_COLOR,
  formatDecimal,
  formatDateTime,
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
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

export default function MyStatementsPage() {
  const [items, setItems] = useState<TechStatement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchStatements() {
    setLoading(true);
    setError(null);
    try {
      // 對帳單路由為 /tenants/{tid}/tech-statements?technician_id=（technicians.id）。
      // 先取 profile 拿 technician_id（JWT sub 為 user_id，非 technicians.id）。
      const profile = await api.get<{ data?: { id: string } }>(
        "/api/v1/technicians/me",
      );
      const techId = profile.data?.id;
      const res = await api.get<TechStatement[] | { items: TechStatement[] }>(
        tenantPath("/tech-statements"),
        techId ? { query: { technician_id: techId } } : undefined,
      );
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

  function renderStatusBadge(status: TechStatement["status"]) {
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

  function renderDeadlineCell(s: TechStatement) {
    if (s.status !== "pending_review" && s.status !== "disputed") {
      return <span className="text-gray-400">—</span>;
    }
    const days = daysUntilDeadline(s.dispute_window_ends_at);
    if (days === null) return <span className="text-gray-400">—</span>;
    if (days < 0)
      return <span className="text-gray-500 italic">已過期</span>;
    if (days < 3)
      return <span className="text-red-600 font-semibold">{days} 天</span>;
    if (days < 7)
      return <span className="text-orange-600 font-semibold">{days} 天</span>;
    return <span className="text-gray-700">{days} 天</span>;
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">我的薪資對帳單</h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0045 — 月薪資對帳 + 申訴流程 (6 state machine)
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
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">完工數</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">毛額</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">扣項</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">淨額</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">申訴期限</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-[var(--bg-surface)]">
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-gray-500">無對帳單</td>
                </tr>
              )}
              {items.map((s) => {
                const totalDeduction =
                  Number(s.travel_fee_deduction) +
                  Number(s.cash_collection_deduction) +
                  Number(s.dispute_hold_amount) +
                  Number(s.other_deductions);
                return (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {s.period_year} / {String(s.period_month).padStart(2, "0")}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">{renderStatusBadge(s.status)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">{s.total_completed_orders}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">{formatDecimal(s.gross_amount)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-orange-600">
                      −{formatDecimal(String(totalDeduction))}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-semibold text-gray-900">
                      {formatDecimal(s.net_amount)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">{renderDeadlineCell(s)}</td>
                  </tr>
                );
              })}
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-gray-500">載入中…</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {items.some((s) => s.status === "disputed") && (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
            <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" />
            <div>
              您有申訴中的對帳單。管理員審核完成前金額暫不撥款，您仍可透過聯絡管理員補充佐證。
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
