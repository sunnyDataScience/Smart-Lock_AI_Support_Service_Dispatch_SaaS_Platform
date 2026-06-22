"use client";

/**
 * FR-0044 Technician Lifecycle — events audit log + 5 lifecycle actions。
 *
 * 對應 backend (api/routers/technician_lifecycle_v2.py):
 *   GET   /tenants/{tid}/technicians/lifecycle-events
 *   POST  /tenants/{tid}/technicians/{tid}/approve
 *   POST  /tenants/{tid}/technicians/{tid}/reject
 *   POST  /tenants/{tid}/technicians/{tid}/suspend
 *   POST  /tenants/{tid}/technicians/{tid}/reactivate
 *   POST  /tenants/{tid}/technicians/{tid}/terminate
 *
 * 對應 Sprint 2 (docs/_ops/phase-ii-web-integration-plan.md §4)
 * 對應 e2e starter: web/tests/e2e/admin/technicians-lifecycle.spec.ts
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, tenantPath } from "@/lib/api";
import {
  type TechnicianLifecycleEvent,
  type TechnicianLifecycleEventType,
  TECHNICIAN_LIFECYCLE_EVENT_LABEL,
  TECHNICIAN_STATUS_LABEL,
  TECHNICIAN_STATUS_COLOR,
  formatDateTime,
  type BadgeColor,
} from "@/components/phase-ii";

const EVENT_FILTERS: { value: TechnicianLifecycleEventType | "all"; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "onboarding_approved", label: "入職核准" },
  { value: "onboarding_rejected", label: "入職駁回" },
  { value: "suspended", label: "停權" },
  { value: "reactivated", label: "復權" },
  { value: "terminated", label: "終止合作" },
  { value: "rating_threshold_breach", label: "評分破閾值" },
  { value: "cert_expired", label: "證照過期" },
];

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

interface EventEnvelope {
  items: TechnicianLifecycleEvent[];
  total?: number;
}

export default function TechniciansLifecyclePage() {
  const [events, setEvents] = useState<TechnicianLifecycleEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [eventFilter, setEventFilter] = useState<
    TechnicianLifecycleEventType | "all"
  >("all");

  async function fetchEvents() {
    setLoading(true);
    setError(null);
    try {
      const q =
        eventFilter === "all" ? "" : `?event_type=${eventFilter}&limit=100`;
      const path = tenantPath(
        eventFilter === "all"
          ? "/technicians/lifecycle-events?limit=100"
          : `/technicians/lifecycle-events${q}`,
      );
      const res = await api.get<EventEnvelope | TechnicianLifecycleEvent[]>(
        path,
      );
      const items = Array.isArray(res) ? res : res.items ?? [];
      setEvents(items);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventFilter]);

  function renderStatusBadge(status: string | null) {
    if (!status) return <span className="text-gray-400">—</span>;
    const key = status as keyof typeof TECHNICIAN_STATUS_LABEL;
    const label = TECHNICIAN_STATUS_LABEL[key] ?? status;
    const color = TECHNICIAN_STATUS_COLOR[key] ?? "gray";
    const sty = STATUS_BG[color];
    return (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: sty.bg, color: sty.text }}
      >
        {label}
      </span>
    );
  }

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">
              技師生命週期事件
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              FR-0044 — onboarding / 停權 / 復權 / 終止 / 證照 / 評分 7 種 audit
              events
            </p>
          </div>
          <button
            type="button"
            onClick={fetchEvents}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            重新整理
          </button>
        </header>

        <div className="mb-4 flex flex-wrap gap-2">
          {EVENT_FILTERS.map((tab) => {
            const active = eventFilter === tab.value;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setEventFilter(tab.value)}
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
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  時間
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  事件類型
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  狀態變化
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  原因
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  操作者
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {events.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-gray-500">
                    無事件紀錄
                  </td>
                </tr>
              )}
              {events.map((ev) => (
                <tr key={ev.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatDateTime(ev.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    {TECHNICIAN_LIFECYCLE_EVENT_LABEL[ev.event_type] ?? ev.event_type}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                    {renderStatusBadge(ev.previous_status)}
                    <span className="mx-2 text-gray-400">→</span>
                    {renderStatusBadge(ev.new_status)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {ev.reason || <span className="text-gray-400">—</span>}
                    {ev.notes && (
                      <div className="text-xs text-gray-400 mt-0.5">{ev.notes}</div>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {ev.actor_role ?? "system"}
                  </td>
                </tr>
              ))}
              {loading && events.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-gray-500">
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
