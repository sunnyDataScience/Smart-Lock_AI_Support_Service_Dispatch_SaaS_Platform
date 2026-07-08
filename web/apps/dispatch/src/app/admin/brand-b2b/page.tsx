"use client";

/**
 * FR-0047 Brand B2B Settlement — AR/AP/NET 對品牌商分帳。
 *
 * 對應 backend: GET /tenants/{tid}/brand-b2b-statements
 * 對應 Sprint 4 (docs/_ops/phase-ii-web-integration-plan.md §4)
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import { api, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import {
  type BrandB2BStatement,
  type B2BDirection,
  STATEMENT_STATUS_LABEL,
  STATEMENT_STATUS_COLOR,
  B2B_DIRECTION_LABEL,
  B2B_DIRECTION_COLOR,
  formatDecimal,
  type BadgeColor,
} from "@shared/components/phase-ii";

const DIRECTION_TABS: { value: B2BDirection | "all"; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "AR", label: "應收 (AR)" },
  { value: "AP", label: "應付 (AP)" },
  { value: "NET", label: "淨額 (NET)" },
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

export default function BrandB2BPage() {
  const [items, setItems] = useState<BrandB2BStatement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [direction, setDirection] = useState<B2BDirection | "all">("all");

  async function fetch() {
    setLoading(true);
    setError(null);
    try {
      const q = direction === "all" ? "" : `?direction=${direction}`;
      const res = await api.get<BrandB2BStatement[] | { items: BrandB2BStatement[] }>(
        tenantPath(`/brand-b2b-statements${q}`),
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
  }, [direction]);

  function renderStatus(s: BrandB2BStatement) {
    const c = STATEMENT_STATUS_COLOR[s.status];
    const sty = COLOR_BG[c];
    return (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {STATEMENT_STATUS_LABEL[s.status]}
      </span>
    );
  }

  function renderDirection(s: BrandB2BStatement) {
    const c = B2B_DIRECTION_COLOR[s.direction];
    const sty = COLOR_BG[c];
    return (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {B2B_DIRECTION_LABEL[s.direction]}
      </span>
    );
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">品牌商 B2B 分帳</h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0047 — AR/AP/NET 三方向 + net_payable_to (brand/platform)
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
          {DIRECTION_TABS.map((tab) => {
            const active = direction === tab.value;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setDirection(tab.value)}
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
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">月份</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">品牌</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">方向</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">狀態</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">應收</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">應付</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">淨額</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">收 / 付</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-sm text-gray-500">無對帳單</td>
                </tr>
              )}
              {items.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    {s.period_year}/{String(s.period_month).padStart(2, "0")}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">{s.brand_name}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderDirection(s)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm">{renderStatus(s)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-blue-700">
                    {formatDecimal(s.ar_service_fee)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-orange-600">
                    {formatDecimal(s.ap_commission)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-semibold text-gray-900">
                    {formatDecimal(s.net_amount)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {s.net_payable_to === "brand" && "→ 付品牌"}
                    {s.net_payable_to === "platform" && "← 收平台"}
                    {!s.net_payable_to && <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              ))}
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-sm text-gray-500">載入中…</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
