"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Wrench, Star, ShieldCheck } from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import StatusEarningsPill from "@/components/tech/dashboard/StatusEarningsPill";
import GoOnlineToggle from "@/components/tech/dashboard/GoOnlineToggle";
import TodayScheduleSummary from "@/components/tech/dashboard/TodayScheduleSummary";
import NeedsAttention from "@/components/tech/dashboard/NeedsAttention";
import WorkloadHeatmap, {
  type WorkloadData,
} from "@/components/tech/dashboard/WorkloadHeatmap";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, tenantPath } from "@/lib/api";
import { formatDecimal, type TechStatement } from "@/components/phase-ii";
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
  const [workload, setWorkload] = useState<WorkloadData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);

    // 1) 先取 profile 拿 technician_id（technicians.id，非 JWT sub 的 user_id）。
    //    工單 / 對帳單 / 負載皆以 technicians.id 過濾，故須先取得。
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
      // profile 失敗則其餘略過（多半未登入 / 401）
    }

    // 2) 以 techId 平行抓工單 / 對帳單 / 負載
    const [ordersRes, stmtsRes, wlRes] = await Promise.allSettled([
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
      techId
        ? api.get<{ data: WorkloadData }>(
            `/api/v1/technicians/${encodeURIComponent(techId)}/workload-heatmap`,
            { query: { days: 30 } },
          )
        : Promise.resolve(null),
    ]);

    if (ordersRes.status === "fulfilled" && ordersRes.value) {
      setOrders(ordersRes.value.items ?? []);
    }
    if (stmtsRes.status === "fulfilled" && stmtsRes.value) {
      const res = stmtsRes.value;
      setStatements(Array.isArray(res) ? res : (res.items ?? []));
    }
    if (wlRes.status === "fulfilled" && wlRes.value) {
      setWorkload(wlRes.value.data ?? null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // 本月已結淨額（approved/paid 之當月對帳單 net_amount）
  const earningsLabel = useMemo(() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    const cur = statements.find(
      (s) =>
        s.period_year === y &&
        s.period_month === m &&
        (s.status === "approved" || s.status === "paid"),
    );
    return cur && cur.net_amount ? formatDecimal(cur.net_amount) : null;
  }, [statements]);

  const greeting = tech?.name ? t("greeting", { name: tech.name }) : t("title");

  return (
    <TechShell wide>
      {/* header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-white px-4 py-3 md:px-6">
        <h1 className="text-[18px] font-semibold text-[#1E293B]">{greeting}</h1>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-page)] disabled:opacity-50"
          title={t("refresh")}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="flex flex-col gap-4 p-4 md:p-6">
        {/* hero：膠囊 + 上線大鈕（桌面並排）*/}
        <div className="grid gap-4 md:grid-cols-2">
          <StatusEarningsPill
            availability={availability}
            amountLabel={earningsLabel}
            caption={t("status.earningsCaption")}
          />
          <div className="flex items-center justify-center rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <GoOnlineToggle
              availability={availability}
              onChanged={(next) => setAvailability(next)}
            />
          </div>
        </div>

        {/* 主內容：桌面雙欄（左 今日行程+案量 / 右 需注意+績效）*/}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <TodayScheduleSummary orders={orders} loading={loading} />
            <WorkloadHeatmap workload={workload} loading={loading} />
          </div>
          <div className="flex flex-col gap-4">
            <NeedsAttention orders={orders} statements={statements} />
            {/* 績效卡片（漸進揭露，次要）*/}
            <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-[15px] font-semibold text-[var(--text-primary)]">
                {t("performance.title")}
              </h2>
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border border-[var(--border)] p-3 text-center">
                  <Wrench className="mx-auto h-4 w-4 text-[var(--text-secondary)]" />
                  <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
                    {tech?.completed_orders_count ?? "—"}
                  </span>
                  <span className="text-[10px] text-[var(--text-disabled)]">
                    {t("performance.completed")}
                  </span>
                </div>
                <div className="rounded-lg border border-[var(--border)] p-3 text-center">
                  <Star className="mx-auto h-4 w-4 fill-amber-400 text-amber-400" />
                  <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
                    {tech?.rating != null ? tech.rating.toFixed(1) : "—"}
                  </span>
                  <span className="text-[10px] text-[var(--text-disabled)]">
                    {t("performance.rating")}
                  </span>
                </div>
                <div className="rounded-lg border border-[var(--border)] p-3 text-center">
                  <ShieldCheck className="mx-auto h-4 w-4 text-[var(--text-secondary)]" />
                  <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
                    {tech?.level ?? "—"}
                  </span>
                  <span className="text-[10px] text-[var(--text-disabled)]">
                    {t("performance.level")}
                  </span>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </TechShell>
  );
}
