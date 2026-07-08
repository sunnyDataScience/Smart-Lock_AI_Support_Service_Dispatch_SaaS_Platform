"use client";

/**
 * FR-0049 Approval Inbox — 統一聚合 5 type pending approval task。
 *
 * 對應 backend: GET /tenants/{tid}/approval-inbox?type=...&limit=N
 * 對應 Sprint 1 (docs/_ops/phase-ii-web-integration-plan.md §4 / wbs-100-closeout-plan.md §1)
 * 對應 e2e starter: web/tests/e2e/admin/approval-inbox.spec.ts
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import {
  type ApprovalInboxResponse,
  type ApprovalInboxItem,
  type ApprovalInboxItemType,
  APPROVAL_INBOX_TYPE_LABEL,
  SEVERITY_LABEL,
  SEVERITY_COLOR,
  formatDateTime,
  type BadgeColor,
} from "@shared/components/phase-ii";

const TYPE_TABS: { value: ApprovalInboxItemType | "all"; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "scope_change", label: "範圍變更" },
  { value: "refund", label: "退款" },
  { value: "dispute", label: "申訴" },
  { value: "reschedule", label: "改期" },
  { value: "recon_exception", label: "對帳例外" },
];

const SEVERITY_BG: Record<BadgeColor, { bg: string; text: string }> = {
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

export default function ApprovalInboxPage() {
  const [data, setData] = useState<ApprovalInboxResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<
    ApprovalInboxItemType | "all"
  >("all");

  async function fetchInbox() {
    setLoading(true);
    setError(null);
    try {
      const path =
        typeFilter === "all"
          ? tenantPath("/approval-inbox?limit=100")
          : tenantPath(`/approval-inbox?type=${typeFilter}&limit=100`);
      const res = await api.get<ApprovalInboxResponse>(path);
      setData(res);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchInbox();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeFilter]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">
              統一審批工作箱
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0049 — 聚合 5 種待審批任務（範圍變更 / 退款 / 申訴 / 改期 / 對帳例外）
            </p>
          </div>
          <button
            type="button"
            onClick={fetchInbox}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw
              size={16}
              className={loading ? "animate-spin" : ""}
            />
            重新整理
          </button>
        </header>

        {/* Type filter tabs */}
        <div className="mb-4 flex flex-wrap gap-2">
          {TYPE_TABS.map((tab) => {
            const count =
              tab.value === "all"
                ? data?.total ?? 0
                : data?.by_type?.[tab.value] ?? 0;
            const active = typeFilter === tab.value;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setTypeFilter(tab.value)}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                }`}
              >
                {tab.label}
                <span
                  className={`ml-2 inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs ${
                    active ? "bg-blue-700" : "bg-gray-200 text-gray-700"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Summary */}
        {data && (
          <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4">
            <div className="text-sm text-gray-500">
              待處理總數：
              <span className="ml-2 text-lg font-semibold text-gray-900">
                {data.total}
              </span>
              <span className="ml-1">件</span>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Items table */}
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  類型
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  嚴重度
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  摘要
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  逾期 (天)
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  建立時間
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {data && data.items.length === 0 && !loading && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-sm text-gray-500"
                  >
                    無待處理項目
                  </td>
                </tr>
              )}
              {data?.items.map((item: ApprovalInboxItem) => {
                const sevColor = SEVERITY_COLOR[item.severity];
                const sevStyle = SEVERITY_BG[sevColor];
                return (
                  <tr key={`${item.type}-${item.id}`} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {APPROVAL_INBOX_TYPE_LABEL[item.type]}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{
                          backgroundColor: sevStyle.bg,
                          color: sevStyle.text,
                        }}
                      >
                        {SEVERITY_LABEL[item.severity]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {item.summary}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {item.days_overdue > 0 ? (
                        <span
                          className={
                            item.days_overdue >= 7
                              ? "font-semibold text-red-600"
                              : item.days_overdue >= 3
                                ? "font-semibold text-orange-600"
                                : "text-gray-700"
                          }
                        >
                          {item.days_overdue}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                      {formatDateTime(item.created_at)}
                    </td>
                  </tr>
                );
              })}
              {loading && !data && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-sm text-gray-500"
                  >
                    載入中…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
