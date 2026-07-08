"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CircleDashed,
  Send,
  CircleCheck,
  Timer,
  Search,
  ChevronDown,
  RefreshCw,
} from "lucide-react";
import Sidebar from "@shared/components/layout/Sidebar";
import DispatchQueueTable from "@/components/dispatch-queue/DispatchQueueTable";
import { api, auth, tenantPath } from "@shared/lib/api";
import { friendlyError } from "@shared/lib/apiError";
import { useLocale, useTranslations } from "@shared/components/i18n/LocaleProvider";
import type { components } from "@shared/types/api.generated";

type DispatchQueueSnapshot = components["schemas"]["DispatchQueueSnapshot"];
type DispatchLog = components["schemas"]["DispatchLog"];
type DispatchLogPage = components["schemas"]["DispatchLogPage"];
type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const URGENCY_TONE: Record<NonNullable<WorkOrder["urgency"]>, { bg: string; text: string }> = {
  high: { bg: "#FEE2E2", text: "#B91C1C" },
  medium: { bg: "#FEF3C7", text: "#B45309" },
  low: { bg: "#DCFCE7", text: "#15803D" },
};

interface CardConfig {
  key: keyof DispatchQueueSnapshot;
  borderColor: string;
  iconColor: string;
  icon: React.ElementType;
}

const cardConfigs: CardConfig[] = [
  {
    key: "pending",
    borderColor: "#F59E0B",
    iconColor: "#F59E0B",
    icon: CircleDashed,
  },
  {
    key: "assigning",
    borderColor: "#3B82F6",
    iconColor: "#3B82F6",
    icon: Send,
  },
  {
    key: "assigned",
    borderColor: "#10B981",
    iconColor: "#10B981",
    icon: CircleCheck,
  },
  {
    key: "sla_at_risk",
    borderColor: "#EF4444",
    iconColor: "#EF4444",
    icon: Timer,
  },
];

export default function DispatchQueuePage() {
  const t = useTranslations("admin.dispatchQueue");
  const tCards = useTranslations("admin.dispatchQueue.cards");
  const tUrgency = useTranslations("admin.dispatchQueue.urgency");
  const { locale } = useLocale();
  const formatTime = useMemo(
    () => (d: Date) => d.toLocaleTimeString(locale, { hour12: false }),
    [locale],
  );
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [dispatchCountFilter, setDispatchCountFilter] = useState<string>("");
  const [responseStatusFilter, setResponseStatusFilter] = useState<string>("");
  const [snapshot, setSnapshot] = useState<DispatchQueueSnapshot | null>(null);
  const [logs, setLogs] = useState<DispatchLog[]>([]);
  const [pool, setPool] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  // v2 tenant-scoped dispatch path helpers（CR-0002-α M06 Dispatch 遷移）
  // 候選技師查詢：GET  /tenants/${tenantId}/dispatch:candidates?work_order_id=...
  // 自動匹配：    POST /tenants/${tenantId}/dispatch:auto-match
  const tenantId = auth.getTenantId();

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [snap, page, poolPage] = await Promise.all([
        api.get<DispatchQueueSnapshot>(tenantPath("/dispatch/queue")),
        api.get<DispatchLogPage>(tenantPath("/dispatch-logs"), {
          query: { limit: 50 },
        }),
        api.get<WorkOrderPage>(tenantPath("/work-orders/pool")),
      ]);
      setSnapshot(snap);
      const items: DispatchLog[] = page.items ?? [];
      setLogs(items);
      setPool(poolPage.items ?? []);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  // client-side filter for pool
  const filteredPool = useMemo(() => {
    const dispatchCounts = new Map<string, number>();
    logs.forEach((log: any) => {
      if (log.work_order_id) {
        dispatchCounts.set(log.work_order_id, (dispatchCounts.get(log.work_order_id) ?? 0) + 1);
      }
    });

    return pool.filter((wo: any) => {
      // keyword: id / customer / address
      if (keyword.trim()) {
        const q = keyword.trim().toLowerCase();
        const matchId = wo.id?.toLowerCase().includes(q);
        const matchName = wo.customer_name?.toLowerCase().includes(q);
        const matchAddr = wo.customer_address?.toLowerCase().includes(q);
        if (!matchId && !matchName && !matchAddr) return false;
      }
      // dispatch count
      if (dispatchCountFilter) {
        const n = dispatchCounts.get(wo.id) ?? 0;
        const threshold = parseInt(dispatchCountFilter, 10);
        if (dispatchCountFilter === "1") {
          if (n !== 1) return false;
        } else if (n < threshold) return false;
      }
      // response status
      if (responseStatusFilter && wo.status !== responseStatusFilter) return false;
      // urgent
      if (urgentOnly && !wo.urgent && wo.priority !== "high") return false;
      return true;
    });
  }, [pool, logs, keyword, dispatchCountFilter, responseStatusFilter, urgentOnly]);

  return (
    // data-tenant 供 E2E 測試驗證 tenant-scoped dispatch v2 路徑（CR-0002-α）
    <div className="flex h-full bg-[var(--bg-page)]" data-tenant={tenantId}>
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-6 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-5">
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {t("breadcrumb")}
              </span>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                  {t("title")}
                </h1>
                <span
                  className="flex items-center gap-[6px] rounded-full px-3 py-1 text-xs font-medium"
                  style={{
                    backgroundColor: error ? "#FEE2E2" : "#DCFCE7",
                    color: error ? "#B91C1C" : "#15803D",
                  }}
                >
                  <span
                    className="h-[6px] w-[6px] rounded-full"
                    style={{ backgroundColor: error ? "#DC2626" : "#22C55E" }}
                  />
                  {error ? t("connection.fail") : t("connection.ok")}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <DispatchModeSelector />
              <span className="text-sm text-[var(--text-secondary)]">
                {updatedAt
                  ? t("lastUpdated", { time: formatTime(updatedAt) })
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

          <div className="grid grid-cols-4 gap-4">
            {cardConfigs.map((card) => {
              const value = snapshot?.[card.key];
              const display =
                loading && snapshot === null
                  ? "—"
                  : value != null
                    ? String(value)
                    : "—";
              return (
                <div
                  key={card.key}
                  className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
                  style={{
                    borderLeftWidth: 4,
                    borderLeftColor: card.borderColor,
                  }}
                >
                  <card.icon
                    className="h-6 w-6 shrink-0"
                    style={{ color: card.iconColor }}
                  />
                  <div className="flex flex-col gap-[2px]">
                    <span className="text-xs font-medium text-[var(--text-secondary)]">
                      {tCards(`${card.key}.title`)}
                    </span>
                    <span className="text-3xl font-bold text-[var(--text-primary)]">
                      {display}
                    </span>
                    <span className="text-xs text-[var(--text-disabled)]">
                      {tCards(`${card.key}.subtitle`)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-3">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3">
            <Search className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("search.placeholder")}
              className="h-9 flex-1 bg-transparent text-sm outline-none"
            />
          </div>

          <select
            value={dispatchCountFilter}
            onChange={(e) => setDispatchCountFilter(e.target.value)}
            className="h-9 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-sm outline-none"
          >
            <option value="">{t("filters.dispatchCount")}</option>
            <option value="1">派工 1 次</option>
            <option value="2">派工 ≥ 2 次</option>
            <option value="3">派工 ≥ 3 次（多次重派）</option>
          </select>

          <select
            value={responseStatusFilter}
            onChange={(e) => setResponseStatusFilter(e.target.value)}
            className="h-9 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 text-sm outline-none"
          >
            <option value="">{t("filters.responseStatus")}</option>
            <option value="dispatched">已派工</option>
            <option value="accepted">技師已接</option>
            <option value="declined">技師婉拒</option>
            <option value="completed">已完工</option>
          </select>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setUrgentOnly((prev) => !prev)}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                urgentOnly ? "bg-[var(--primary)]" : "bg-[#CBD5E1]"
              }`}
            >
              <span
                className={`absolute top-[2px] h-4 w-4 rounded-full bg-white transition-transform ${
                  urgentOnly ? "left-[18px]" : "left-[2px]"
                }`}
              />
            </button>
            <span className="text-sm text-[var(--text-secondary)]">
              {t("filters.needIntervention")}
            </span>
          </div>
        </div>

        <div className="flex flex-1 min-h-0 flex-col gap-4 overflow-auto px-8 py-5">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                {t("pool.title")}
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                {t("pool.summary", { count: String(filteredPool.length) })}
              </span>
            </div>
            {filteredPool.length === 0 ? (
              <div className="flex h-20 items-center justify-center text-sm text-[var(--text-secondary)]">
                {t("pool.empty")}
              </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {filteredPool.slice(0, 10).map((wo) => {
                  const urgency = wo.urgency ?? "low";
                  const color = URGENCY_TONE[urgency];
                  return (
                    <Link
                      key={wo.id}
                      href={`/work-orders/${wo.id}`}
                      className="flex items-center gap-4 px-4 py-3 transition hover:bg-[var(--bg-page)]"
                    >
                      <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-secondary)]">
                        #{wo.id.slice(0, 8)}
                      </span>
                      <span
                        className="rounded-md px-2 py-[2px] text-[11px] font-semibold"
                        style={{ backgroundColor: color.bg, color: color.text }}
                      >
                        {tUrgency(urgency)}
                      </span>
                      <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        {wo.brand}
                        {wo.model ? ` / ${wo.model}` : ""}
                      </span>
                      <span className="flex-1 truncate text-[12px] text-[var(--text-secondary)]">
                        {wo.district}
                        {wo.address ? ` · ${wo.address}` : ""}
                      </span>
                      <span className="text-[11px] text-[var(--text-disabled)]">
                        {wo.created_at
                          ? new Date(wo.created_at).toLocaleString(locale, {
                              hour12: false,
                            })
                          : "—"}
                      </span>
                    </Link>
                  );
                })}
              </div>
            )}
            {filteredPool.length > 10 && (
              <div className="border-t border-[var(--border)] px-4 py-2 text-center text-[12px] text-[var(--text-secondary)]">
                {t("pool.more", { count: String(filteredPool.length - 10) })}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-auto">
            <DispatchQueueTable items={logs} loading={loading} />
          </div>
        </div>
      </div>
    </div>
  );
}


// CR-0030 派工模式切換（manual / platform_paid / auto_match）— 管理角色
function DispatchModeSelector() {
  const t = useTranslations("admin.dispatchQueue.dispatchMode");
  const [mode, setMode] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ dispatch_mode: string }>(tenantPath("/dispatch-mode"));
        if (!cancelled) setMode(res.dispatch_mode);
      } catch {
        if (!cancelled) setMode("manual");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onChange(next: string) {
    const prev = mode;
    setMode(next);
    setSaving(true);
    try {
      await api.post(tenantPath("/dispatch-mode"), { mode: next });
    } catch {
      setMode(prev ?? "manual"); // rollback on failure
    } finally {
      setSaving(false);
    }
  }

  if (mode === null) return null;

  return (
    <label className="flex items-center gap-2 text-sm" title={t("hint")}>
      <span className="text-[var(--text-secondary)]">{t("label")}</span>
      <select
        value={mode}
        disabled={saving}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-sm text-[var(--text-primary)] disabled:opacity-60"
      >
        <option value="manual">{t("manual")}</option>
        <option value="platform_paid">{t("platformPaid")}</option>
        <option value="auto_match">{t("autoMatch")}</option>
      </select>
    </label>
  );
}
