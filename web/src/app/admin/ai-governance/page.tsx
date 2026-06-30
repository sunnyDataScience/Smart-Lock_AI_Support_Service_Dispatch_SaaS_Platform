"use client";

/**
 * FR-0050 AI Governance Trace — agent 決策 lineage + guardrail block stats。
 *
 * 對應 backend:
 *   GET /tenants/{tid}/ai-governance/traces
 *   GET /tenants/{tid}/ai-governance/traces/summary
 */

import { useEffect, useState } from "react";
import { RefreshCw, Shield } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { api, tenantPath } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import {
  type AiDecisionTrace,
  type AiGovernanceSummary,
  AI_DECISION_TYPE_LABEL,
  GUARDRAIL_ACTION_LABEL,
  GUARDRAIL_ACTION_COLOR,
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
  return friendlyError(e);
}

export default function AiGovernancePage() {
  const [traces, setTraces] = useState<AiDecisionTrace[]>([]);
  const [summary, setSummary] = useState<AiGovernanceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchAll() {
    setLoading(true);
    setError(null);
    try {
      const [t, s] = await Promise.all([
        api.get<AiDecisionTrace[] | { items: AiDecisionTrace[] }>(
          tenantPath("/ai-governance/traces?limit=100"),
        ),
        api.get<AiGovernanceSummary>(tenantPath("/ai-governance/traces/summary")),
      ]);
      setTraces(Array.isArray(t) ? t : t.items ?? []);
      setSummary(s);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchAll();
  }, []);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={28} className="text-purple-600" />
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">AI 治理追蹤</h1>
              <p className="mt-1 text-sm text-gray-500">
                FR-0050 — agent 決策 lineage + guardrail block 統計
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={fetchAll}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            重新整理
          </button>
        </header>

        {summary && (
          <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs uppercase text-gray-500">總決策數</div>
              <div className="mt-1 text-2xl font-semibold text-gray-900">
                {summary.totals.total_decisions}
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs uppercase text-gray-500">Guardrail 阻擋</div>
              <div className="mt-1 text-2xl font-semibold text-red-600">
                {summary.totals.block_count}
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="text-xs uppercase text-gray-500">阻擋率</div>
              <div className="mt-1 text-2xl font-semibold text-orange-600">
                {summary.totals.block_rate_pct.toFixed(2)}%
              </div>
            </div>
          </div>
        )}

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
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">決策類型</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">摘要</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Guardrail</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Agent 版本</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {traces.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-gray-500">無紀錄</td>
                </tr>
              )}
              {traces.map((tr) => (
                <tr key={tr.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatDateTime(tr.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    {AI_DECISION_TYPE_LABEL[tr.decision_type]}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">{tr.action_summary}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">
                    {tr.guardrail_action ? (
                      (() => {
                        const c = GUARDRAIL_ACTION_COLOR[tr.guardrail_action];
                        const sty = COLOR_BG[c];
                        return (
                          <span
                            className="rounded-full px-2 py-0.5 text-xs font-medium"
                            style={{ backgroundColor: sty.bg, color: sty.text }}
                            title={tr.guardrail_triggered ?? ""}
                          >
                            {GUARDRAIL_ACTION_LABEL[tr.guardrail_action]}
                          </span>
                        );
                      })()
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500 font-mono text-xs">
                    {tr.agent_version ?? "—"}
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
