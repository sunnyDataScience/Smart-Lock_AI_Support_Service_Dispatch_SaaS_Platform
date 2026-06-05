"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RefreshCw, Package, ExternalLink } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import { ApiError, api, auth, tenantPath } from "@/lib/api";
import { useLocale, useTranslations } from "@/components/i18n/LocaleProvider";

/**
 * Flow 4 admin 補料管理彙整視圖 — 跨工單列出活躍的缺料回報。
 * 端點：GET /tenants/{tenantId}/material-requests (listPendingMaterialRequestsV2)
 *
 * MVP 不分 pending vs supplied（後端尚無 supply_arrived event_type 機制）；
 * 此頁提供「最近活躍的缺料事件」清單，admin 點工單 ID 進詳情頁進一步處理。
 */

type Urgency = "now" | "today" | "tomorrow" | "other";

interface MaterialItem {
  brand: string;
  model: string;
  quantity: number;
}

interface MaterialRequestPayload {
  items?: MaterialItem[];
  urgency?: string;
  note?: string;
}

interface MaterialRequestRow {
  event_id: string;
  created_at: string;
  payload: MaterialRequestPayload;
  actor_user_id: string | null;
  work_order_id: string;
  wo_status: string;
  scheduled_at: string | null;
  technician_id: string | null;
}

interface MaterialRequestListResponse {
  items: MaterialRequestRow[];
  count: number;
}

const URGENCY_TONE: Record<Urgency, { bg: string; text: string }> = {
  now: { bg: "#FEE2E2", text: "#B91C1C" },
  today: { bg: "#FEF3C7", text: "#B45309" },
  tomorrow: { bg: "#DCFCE7", text: "#15803D" },
  other: { bg: "#E5E7EB", text: "#374151" },
};

const URGENCY_ORDER: Record<Urgency, number> = {
  now: 0,
  today: 1,
  tomorrow: 2,
  other: 9,
};

function normalizeUrgency(raw: string | undefined): Urgency {
  if (raw === "now" || raw === "today" || raw === "tomorrow") return raw;
  return "other";
}

function summarizeItems(items: MaterialItem[] | undefined, fallback: string): string {
  if (!items || items.length === 0) return fallback;
  return items.map((it) => `${it.brand} ${it.model} ×${it.quantity}`).join("、");
}

export default function AdminMaterialRequestsPage() {
  const t = useTranslations("admin.materialRequests");
  const { locale } = useLocale();
  const formatDateTime = useMemo(
    () => (iso: string | null) => {
      if (!iso) return "—";
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toLocaleString(locale, { hour12: false });
    },
    [locale],
  );

  const tenantId = auth.getTenantId();

  const [rows, setRows] = useState<MaterialRequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [urgencyFilter, setUrgencyFilter] = useState<Urgency | "all">("all");

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<MaterialRequestListResponse>(
        tenantPath("/material-requests"),
        { query: { limit: 200 } },
      );
      setRows(resp.items ?? []);
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
    fetchAll();
  }, []);

  const filtered = useMemo(() => {
    if (urgencyFilter === "all") return rows;
    return rows.filter((r) => normalizeUrgency(r.payload.urgency) === urgencyFilter);
  }, [rows, urgencyFilter]);

  const countByUrgency = useMemo(() => {
    const acc: Record<Urgency, number> = { now: 0, today: 0, tomorrow: 0, other: 0 };
    for (const r of rows) acc[normalizeUrgency(r.payload.urgency)] += 1;
    return acc;
  }, [rows]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]" data-tenant={tenantId}>
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {t("breadcrumb")}
              </span>
              <div className="flex items-center gap-3">
                <Package className="h-6 w-6 text-[var(--text-primary)]" />
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                  {t("title")}
                </h1>
                <span className="text-sm text-[var(--text-secondary)]">
                  {t("count", { n: rows.length })}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-[var(--text-secondary)]">
                {updatedAt
                  ? t("lastUpdated", { time: updatedAt.toLocaleTimeString(locale, { hour12: false }) })
                  : t("notLoaded")}
              </span>
              <button
                onClick={fetchAll}
                disabled={loading}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title={t("refresh")}
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
                />
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex items-center gap-2">
            {(["all", "now", "today", "tomorrow", "other"] as const).map((u) => {
              const isActive = urgencyFilter === u;
              const n = u === "all" ? rows.length : countByUrgency[u];
              return (
                <button
                  key={u}
                  onClick={() => setUrgencyFilter(u)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    isActive
                      ? "bg-[var(--text-primary)] text-white"
                      : "bg-[var(--bg-page)] text-[var(--text-secondary)] hover:bg-[var(--border)]"
                  }`}
                >
                  {t(`filter.${u}`)} ({n})
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex-1 overflow-auto px-4 md:px-8 py-6">
          {loading && rows.length === 0 ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-8 text-center text-sm text-[var(--text-secondary)]">
              {t("loading")}
            </div>
          ) : filtered.length === 0 ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-8 text-center text-sm text-[var(--text-secondary)]">
              {t("empty")}
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--border)] bg-[var(--bg-page)] text-xs uppercase text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-4 py-3 text-left">{t("col.urgency")}</th>
                    <th className="px-4 py-3 text-left">{t("col.reportedAt")}</th>
                    <th className="px-4 py-3 text-left">{t("col.workOrder")}</th>
                    <th className="px-4 py-3 text-left">{t("col.woStatus")}</th>
                    <th className="px-4 py-3 text-left">{t("col.scheduledAt")}</th>
                    <th className="px-4 py-3 text-left">{t("col.items")}</th>
                    <th className="px-4 py-3 text-left">{t("col.note")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => {
                    const u = normalizeUrgency(r.payload.urgency);
                    const tone = URGENCY_TONE[u];
                    return (
                      <tr
                        key={r.event_id}
                        className="border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--bg-page)]"
                      >
                        <td className="px-4 py-3">
                          <span
                            className="inline-flex rounded-full px-2.5 py-1 text-xs font-medium"
                            style={{ backgroundColor: tone.bg, color: tone.text }}
                          >
                            {t(`filter.${u}`)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">
                          {formatDateTime(r.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <Link
                            href={`/work-orders/${r.work_order_id}`}
                            className="inline-flex items-center gap-1 font-mono text-xs text-blue-600 hover:underline"
                          >
                            {r.work_order_id.slice(0, 8)}
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">
                          {r.wo_status}
                        </td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">
                          {formatDateTime(r.scheduled_at)}
                        </td>
                        <td className="px-4 py-3 text-[var(--text-primary)]">
                          {summarizeItems(r.payload.items, t("noItems"))}
                        </td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">
                          {r.payload.note || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
