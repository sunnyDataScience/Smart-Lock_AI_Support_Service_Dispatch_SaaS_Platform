"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, ClipboardList, RefreshCw } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import StatusBadge from "@/components/tech/StatusBadge";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import { ApiError, api, getCurrentSession } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

type TabKey = "active" | "pending" | "history";

const TABS: { value: TabKey; label: string; statuses: WorkOrderStatus[] }[] = [
  {
    value: "active",
    label: "進行中",
    statuses: [
      "accepted",
      "scheduled",
      "assigned",
      "en_route",
      "arrived",
      "in_progress",
    ],
  },
  {
    value: "pending",
    label: "待確認",
    statuses: ["completed", "billed"],
  },
  {
    value: "history",
    label: "歷史",
    statuses: ["paid", "closed", "cancelled"],
  },
];

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function MyOrdersPage() {
  const [tab, setTab] = useState<TabKey>("active");
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const technicianId = useMemo(() => {
    const session = getCurrentSession();
    return session?.userId ?? null;
  }, []);

  const fetchList = useCallback(async () => {
    if (!technicianId) {
      setError("尚未登入或無法取得技師身份");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const query: Record<string, string | number> = {
        technician_id: technicianId,
        limit: 50,
      };
      const res = await api.get<WorkOrderPage>("/api/v1/work-orders", {
        query,
      });
      setItems(res.items ?? []);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, [technicianId]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const tabStatuses = TABS.find((t) => t.value === tab)?.statuses ?? [];
  const visible = items.filter((x) => tabStatuses.includes(x.status));
  const counts = TABS.reduce<Record<TabKey, number>>(
    (acc, t) => {
      acc[t.value] = items.filter((x) => t.statuses.includes(x.status)).length;
      return acc;
    },
    { active: 0, pending: 0, history: 0 },
  );

  return (
    <TechShell>
      {/* page_header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-white px-4 py-3">
        <h1 className="text-[18px] font-semibold text-[#1E293B]">我的工單</h1>
        <button
          type="button"
          onClick={fetchList}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title="重新整理"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* tab_bar */}
      <div className="sticky top-[57px] z-10 grid grid-cols-3 border-b border-[var(--border)] bg-white">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={`relative flex h-12 items-center justify-center gap-1 text-[14px] font-medium ${
              tab === t.value
                ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                : "text-[#64748B]"
            }`}
          >
            {t.label}
            {counts[t.value] > 0 && (
              <span
                className={`min-w-[18px] rounded-full px-[6px] py-[1px] text-[10px] font-bold ${
                  tab === t.value
                    ? "bg-[var(--primary)] text-white"
                    : "bg-[#E2E8F0] text-[#475569]"
                }`}
              >
                {counts[t.value]}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3 px-4 py-4">
        {loading && items.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            載入中…
          </div>
        ) : visible.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
            <ClipboardList className="h-10 w-10 text-[var(--text-disabled)]" />
            <p className="text-[14px]">
              {tab === "active"
                ? "目前沒有進行中的工單"
                : tab === "pending"
                  ? "沒有待確認工單"
                  : "沒有歷史工單"}
            </p>
            {tab === "active" && (
              <Link
                href="/pool"
                className="mt-2 rounded-md bg-[var(--primary)] px-3 py-2 text-[12px] font-semibold text-white"
              >
                前往案件池接單
              </Link>
            )}
          </div>
        ) : (
          visible.map((wo) => (
            <Link
              key={wo.id}
              href={`/my-orders/${wo.id}`}
              className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm transition hover:bg-[var(--bg-page)]"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-[11px] text-[var(--text-disabled)]">
                  #{wo.id.slice(0, 8)}
                </span>
                <div className="flex items-center gap-1">
                  <UrgencyBadge urgency={wo.urgency} />
                  <StatusBadge status={wo.status} />
                </div>
              </div>
              <h3 className="text-[15px] font-semibold text-[var(--text-primary)] line-clamp-2">
                {wo.address}
              </h3>
              <div className="flex items-center gap-2 text-[12px] text-[var(--text-secondary)]">
                <span className="rounded bg-[#F1F5F9] px-2 py-[2px]">
                  {wo.brand} {wo.model}
                </span>
                <span>·</span>
                <span>{wo.district}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-[var(--text-disabled)]">
                <span>{formatRelative(wo.updated_at)}</span>
                <ChevronRight className="h-4 w-4" />
              </div>
            </Link>
          ))
        )}
      </div>
    </TechShell>
  );
}
