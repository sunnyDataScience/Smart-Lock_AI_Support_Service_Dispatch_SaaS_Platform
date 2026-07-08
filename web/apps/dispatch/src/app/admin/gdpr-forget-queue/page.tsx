"use client";

/**
 * FR-0053 GDPR Forget Request — T0 soft + T+30 hard delete queue。
 *
 * 對應 backend: GET /tenants/{tid}/gdpr/forget-requests
 * 對應 Sprint 4 (docs/_ops/phase-ii-web-integration-plan.md §4)
 */

import { useEffect, useState } from "react";
import { RefreshCw, Shield } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import {
  type GdprForgetRequest,
  type GdprForgetStatus,
  GDPR_FORGET_STATUS_LABEL,
  GDPR_FORGET_STATUS_COLOR,
  GDPR_REQUESTED_BY_LABEL,
  formatDateTime,
  daysUntilDeadline,
  type BadgeColor,
} from "@shared/components/phase-ii";

const STATUS_TABS: { value: GdprForgetStatus | "all"; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "received", label: "已收件" },
  { value: "legal_hold_denied", label: "法務扣留" },
  { value: "soft_deleted", label: "軟刪除" },
  { value: "hard_deleted", label: "硬刪除" },
  { value: "cancelled", label: "已取消" },
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

export default function GdprForgetQueuePage() {
  const [items, setItems] = useState<GdprForgetRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<GdprForgetStatus | "all">("all");

  async function fetch() {
    setLoading(true);
    setError(null);
    try {
      const q = status === "all" ? "" : `?status=${status}`;
      const res = await api.get<GdprForgetRequest[] | { items: GdprForgetRequest[] }>(
        tenantPath(`/gdpr/forget-requests${q}`),
      );
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
  }, [status]);

  function renderBadge(s: GdprForgetStatus) {
    const c = GDPR_FORGET_STATUS_COLOR[s];
    const sty = COLOR_BG[c];
    return (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {GDPR_FORGET_STATUS_LABEL[s]}
      </span>
    );
  }

  function renderEligible(it: GdprForgetRequest) {
    if (it.status !== "soft_deleted") return <span className="text-gray-400">—</span>;
    const days = daysUntilDeadline(it.hard_delete_eligible_at);
    if (days === null) return <span className="text-gray-400">—</span>;
    if (days <= 0)
      return <span className="text-red-600 font-semibold">可硬刪 (T+30 到)</span>;
    return <span className="text-orange-600">尚餘 {days} 天</span>;
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={28} className="text-blue-600" />
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">GDPR 被遺忘權佇列</h1>
              <p className="mt-1 text-sm text-gray-500">
                FR-0053 — T0 soft delete + T+30 hard delete (BR-PII-001)
              </p>
            </div>
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
          {STATUS_TABS.map((tab) => {
            const active = status === tab.value;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setStatus(tab.value)}
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
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">收件時間</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">當事人</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">請求來源</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">狀態</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">硬刪資格</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">扣留原因</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-gray-500">無申請</td>
                </tr>
              )}
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatDateTime(it.received_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    {it.subject_email ?? <span className="text-gray-400 italic">已遮蔽</span>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    {GDPR_REQUESTED_BY_LABEL[it.requested_by]}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderBadge(it.status)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderEligible(it)}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {it.legal_hold_reason ?? <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              ))}
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-gray-500">載入中…</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
