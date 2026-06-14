"use client";

/**
 * FR-0048 RMA Quality Findings — 失效模式 + repeat failure + AI 診斷準確度。
 *
 * 對應 backend: GET /tenants/{tid}/rma-quality-findings
 */

import { useEffect, useState } from "react";
import { RefreshCw, AlertCircle } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import {
  type RmaQualityFinding,
  AI_DIAGNOSIS_ACCURACY_LABEL,
  AI_DIAGNOSIS_ACCURACY_COLOR,
  formatDateTime,
  type BadgeColor,
} from "@/components/phase-ii";

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
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

export default function RmaQualityPage() {
  const [items, setItems] = useState<RmaQualityFinding[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [repeatOnly, setRepeatOnly] = useState(false);

  async function fetch() {
    setLoading(true);
    setError(null);
    try {
      const q = repeatOnly ? "?is_repeat_failure=true&limit=100" : "?limit=100";
      const res = await api.get<RmaQualityFinding[] | { items: RmaQualityFinding[] }>(
        tenantPath(`/rma-quality-findings${q}`),
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
  }, [repeatOnly]);

  function renderAccuracy(acc: RmaQualityFinding["ai_diagnosis_accuracy"]) {
    if (!acc) return <span className="text-gray-400">—</span>;
    const c = AI_DIAGNOSIS_ACCURACY_COLOR[acc];
    const sty = COLOR_BG[c];
    return (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {AI_DIAGNOSIS_ACCURACY_LABEL[acc]}
      </span>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">RMA 品質追蹤</h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0048 — 失效模式 + repeat failure + AI 診斷準確度
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
          <button
            type="button"
            onClick={() => setRepeatOnly(false)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
              !repeatOnly
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
            }`}
          >
            全部
          </button>
          <button
            type="button"
            onClick={() => setRepeatOnly(true)}
            className={`flex items-center gap-1 rounded-full px-3 py-1.5 text-sm font-medium transition ${
              repeatOnly
                ? "bg-red-600 text-white"
                : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
            }`}
          >
            <AlertCircle size={14} />
            僅看 Repeat Failure
          </button>
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
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">品牌 / 型號</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">失效模式</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Repeat</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">品牌品質</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">技師品質</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">AI 診斷</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">CSAT</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-sm text-gray-500">無紀錄</td>
                </tr>
              )}
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatDateTime(it.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    {it.brand ?? "—"}
                    {it.device_model && (
                      <span className="text-xs text-gray-400 ml-1">/ {it.device_model}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 font-medium">{it.failure_mode}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">
                    {it.is_repeat_failure ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                        <AlertCircle size={12} />
                        重複
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {it.brand_quality_score?.toFixed(1) ?? "—"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {it.technician_quality_score?.toFixed(1) ?? "—"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderAccuracy(it.ai_diagnosis_accuracy)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {it.customer_satisfaction_score ?? "—"}
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
