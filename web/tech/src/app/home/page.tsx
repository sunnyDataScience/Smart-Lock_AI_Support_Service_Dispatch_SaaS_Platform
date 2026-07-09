"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import TechHomeHero from "@/components/tech/dashboard/TechHomeHero";
import TodayScheduleSummary from "@/components/tech/dashboard/TodayScheduleSummary";
import NeedsAttention from "@/components/tech/dashboard/NeedsAttention";
import RecentFeedback from "@/components/tech/dashboard/RecentFeedback";
import WorkloadHeatmap, {
  type WorkloadData,
} from "@/components/tech/dashboard/WorkloadHeatmap";
import MonthlySnapshot, {
  type DashboardSummary,
  formatNT,
} from "@/components/tech/dashboard/MonthlySnapshot";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, tenantPath } from "@/lib/api";
import { type TechStatement } from "@/components/phase-ii";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];
type Availability = Technician["availability"];
type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

export default function TechHomePage() {
  const t = useTranslations("techPortal.home");
  const [tech, setTech] = useState<Technician | null>(null);
  const [availability, setAvailability] = useState<Availability>("offline");
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [statements, setStatements] = useState<TechStatement[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [workload, setWorkload] = useState<WorkloadData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);

    // 1) 先取 profile：availability / 姓名 / technician_id（工單過濾需 technicians.id）
    let techId: string | null = null;
    try {
      const profileRes = await api.get<TechnicianEnvelope>(
        "/api/v1/technicians/me",
      );
      if (profileRes.data) {
        setTech(profileRes.data);
        setAvailability(profileRes.data.availability);
        techId = profileRes.data.id;
      }
    } catch {
      // 多半未登入 / 401
    }

    // 2) 平行抓：工單(需 techId) / 對帳單(需 techId) / 決策屏聚合(self) / 負載(self)
    const [ordersRes, stmtsRes, summaryRes, wlRes] = await Promise.allSettled([
      techId
        ? api.get<WorkOrderPage>(tenantPath("/work-orders"), {
            query: { technician_id: techId, limit: 50 },
          })
        : Promise.resolve(null),
      techId
        ? api.get<TechStatement[] | { items: TechStatement[] }>(
            tenantPath("/tech-statements"),
            { query: { technician_id: techId } },
          )
        : Promise.resolve(null),
      api.get<{ data: DashboardSummary }>(
        "/api/v1/technicians/me/dashboard-summary",
      ),
      api.get<{ data: WorkloadData }>(
        "/api/v1/technicians/me/workload-heatmap",
        { query: { days: 30 } },
      ),
    ]);

    if (ordersRes.status === "fulfilled" && ordersRes.value) {
      setOrders(ordersRes.value.items ?? []);
    }
    if (stmtsRes.status === "fulfilled" && stmtsRes.value) {
      const res = stmtsRes.value;
      setStatements(Array.isArray(res) ? res : (res.items ?? []));
    }
    if (summaryRes.status === "fulfilled" && summaryRes.value) {
      setSummary(summaryRes.value.data ?? null);
    }
    if (wlRes.status === "fulfilled" && wlRes.value) {
      setWorkload(wlRes.value.data ?? null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // 收入膠囊：上線顯示今日預估、離線顯示本週預估（口徑為 estimated_price 預估）
  const { earningsLabel, earningsCaption } = useMemo(() => {
    if (!summary) {
      return { earningsLabel: null, earningsCaption: t("status.earningsCaption") };
    }
    return availability === "available"
      ? {
          earningsLabel: formatNT(summary.today_earnings),
          earningsCaption: t("status.todayCaption"),
        }
      : {
          earningsLabel: formatNT(summary.week_earnings),
          earningsCaption: t("status.weekCaption"),
        };
  }, [summary, availability, t]);

  const greeting = tech?.name ? t("greeting", { name: tech.name }) : t("title");

  return (
    <TechShell
      wide
      // 頁首走 shell 統一規格(h-14 bar;2026-07-07 頁首一致性)
      title={t("title")}
      actions={
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title={t("refresh")}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      }
    >
      <div className="flex flex-col gap-5 p-4 md:p-6">
        {/* hero：問候 + 狀態 + 收入 + 上線開關收攏為單一視覺錨點 */}
        <TechHomeHero
          greeting={greeting}
          availability={availability}
          amountLabel={earningsLabel}
          amountCaption={earningsCaption}
          onAvailabilityChanged={(next) => setAvailability(next)}
        />

        {/* 本月表現統計條 */}
        <MonthlySnapshot summary={summary} loading={loading} />

        {/* 主內容：桌面雙欄 */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <TodayScheduleSummary orders={orders} loading={loading} />
            <WorkloadHeatmap workload={workload} loading={loading} />
          </div>
          <div className="flex flex-col gap-4">
            <NeedsAttention orders={orders} statements={statements} />
            <RecentFeedback summary={summary} />
          </div>
        </div>
      </div>
    </TechShell>
  );
}
