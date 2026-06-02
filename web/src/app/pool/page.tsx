"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, MapPin, RefreshCw } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import UrgencyBadge from "@/components/tech/UrgencyBadge";
import RealtimeIndicator from "@/components/realtime/RealtimeIndicator";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { ApiError, api, getCurrentSession, tenantPath } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useRealtimeChannel } from "@/hooks/useRealtimeChannel";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];
type WorkOrderEnvelope = components["schemas"]["WorkOrderEnvelope"];

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function PoolPage() {
  const router = useRouter();
  const t = useTranslations("techPortal.pool");
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [conflictMsg, setConflictMsg] = useState<string | null>(null);

  const fetchPool = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<WorkOrderPage>(tenantPath("/work-orders/pool"));
      setItems(res.items ?? []);
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPool();
  }, [fetchPool]);

  const techId = useMemo(() => getCurrentSession()?.userId ?? null, []);

  // 訂閱單一工單變化：他人接走時從列表移除
  const { status: poolStatus } = useRealtimeChannel<{
    work_order_id?: string;
    event?: "added" | "taken" | "cancelled";
    work_order?: WorkOrder;
  }>({
    channelPath: techId ? `/realtime/pool/${techId}` : "",
    enabled: !!techId,
    onMessage: (msg) => {
      const data = (msg.payload ?? msg) as {
        work_order_id?: string;
        event?: "added" | "taken" | "cancelled";
        work_order?: WorkOrder;
      };
      if (data.event === "added" && data.work_order) {
        setItems((prev) =>
          prev.some((x) => x.id === data.work_order!.id)
            ? prev
            : [data.work_order!, ...prev],
        );
      } else if (
        (data.event === "taken" || data.event === "cancelled") &&
        data.work_order_id
      ) {
        setItems((prev) => prev.filter((x) => x.id !== data.work_order_id));
      }
    },
  });

  async function acceptOrder(wo: WorkOrder) {
    if (accepting) return;
    setAccepting(wo.id);
    setError(null);
    setConflictMsg(null);
    try {
      const res = await api.post<WorkOrderEnvelope>(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}:accept`),
      );
      const accepted = res.data;
      if (accepted) {
        router.push(`/my-orders/${accepted.id}`);
      } else {
        router.push(`/my-orders/${wo.id}`);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setConflictMsg(t("conflictTaken"));
        setItems((prev) => prev.filter((x) => x.id !== wo.id));
      } else {
        setError(formatErr(e));
      }
    } finally {
      setAccepting(null);
    }
  }

  return (
    <TechShell>
      {/* Page Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-white px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-[18px] font-semibold text-[#1E293B]">{t("title")}</h1>
            <RealtimeIndicator status={poolStatus} compact />
          </div>
          <p className="text-[12px] text-[var(--text-secondary)]">
            {loading ? t("loading") : t("availableCount", { count: items.length })}
          </p>
        </div>
        <button
          type="button"
          onClick={fetchPool}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title={t("refreshTitle")}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}
      {conflictMsg && (
        <div className="m-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-800">
          {conflictMsg}
        </div>
      )}

      {/* List */}
      <div className="flex flex-col gap-3 px-4 py-4">
        {loading && items.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-[13px] text-[var(--text-secondary)]">
            {t("loading")}
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-60 flex-col items-center justify-center gap-2 text-[var(--text-secondary)]">
            <MapPin className="h-10 w-10 text-[var(--text-disabled)]" />
            <p className="text-[14px]">{t("empty")}</p>
            <button
              type="button"
              onClick={fetchPool}
              className="mt-2 rounded-md border border-[var(--border)] px-3 py-1 text-[12px] font-medium text-[var(--primary)] hover:bg-[#EFF6FF]"
            >
              {t("refreshTitle")}
            </button>
          </div>
        ) : (
          items.map((wo) => {
            const urgencyBorder =
              wo.urgency === "high"
                ? "#EF4444"
                : wo.urgency === "medium"
                  ? "#F59E0B"
                  : "#10B981";
            return (
              <article
                key={wo.id}
                className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm"
                style={{ borderLeftColor: urgencyBorder, borderLeftWidth: 4 }}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[11px] text-[var(--text-disabled)]">
                    #{wo.id.slice(0, 8)}
                  </span>
                  <UrgencyBadge urgency={wo.urgency} />
                </div>
                <h3 className="text-[15px] font-semibold text-[var(--text-primary)] line-clamp-2">
                  {wo.address}
                </h3>
                <div className="flex flex-wrap items-center gap-2 text-[12px] text-[var(--text-secondary)]">
                  <span className="rounded bg-[#F1F5F9] px-2 py-[2px]">
                    {wo.brand} {wo.model}
                  </span>
                  <span className="rounded bg-[#F1F5F9] px-2 py-[2px]">
                    {wo.district}
                  </span>
                  {wo.estimated_reward && (
                    <span className="text-[#059669] font-semibold">
                      {t("estimatedReward", { amount: wo.estimated_reward })}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[11px] text-[var(--text-disabled)]">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatRelative(wo.created_at)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => acceptOrder(wo)}
                  disabled={!!accepting}
                  className="mt-2 h-12 rounded-lg bg-[var(--primary)] text-[15px] font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-60"
                >
                  {accepting === wo.id ? t("accepting") : t("accept")}
                </button>
              </article>
            );
          })
        )}
      </div>
    </TechShell>
  );
}
