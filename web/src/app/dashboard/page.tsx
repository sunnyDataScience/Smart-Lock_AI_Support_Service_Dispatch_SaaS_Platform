"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ClipboardList,
  CircleCheckBig,
  TriangleAlert,
  Users,
  Sparkles,
  Shield,
  MessageSquare,
  Inbox,
  CheckCircle2,
  UserCog,
  Timer,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import KpiCard from "@/components/dashboard/KpiCard";
import WorkOrderTrendChart from "@/components/dashboard/WorkOrderTrendChart";
import TechnicianStatusChart from "@/components/dashboard/TechnicianStatusChart";
import RecentWorkOrders from "@/components/dashboard/RecentWorkOrders";
import HotTopicsCard from "@/components/dashboard/HotTopicsCard";
import LiveRegion from "@/components/ui/LiveRegion";
import DateRangePicker from "@/components/ui/DateRangePicker";
import {
  getPresetRange,
  mapRangeToDashboardPeriod,
  type DateRange,
} from "@/lib/dateRange";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type DashboardStats = components["schemas"]["DashboardStats"];
type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];
type Technician = components["schemas"]["Technician"];
type TechnicianPage = components["schemas"]["TechnicianPage"];

// 統一在 page 層 fetch 工單與技師，避免子元件各自重複 fetch
const WORK_ORDERS_LIMIT = 100;  // /work-orders pydantic le=100
const RECENT_WO_DISPLAY = 5;    // RecentWorkOrders 只顯示前 5 筆
const TECHNICIANS_LIMIT = 100;

function formatDuration(seconds: number | undefined | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} 分`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins === 0 ? `${hours} 時` : `${hours} 時 ${mins} 分`;
}

function formatPercent(rate: number | undefined | null): string {
  if (rate == null) return "—";
  return `${Math.round(rate * 100)}%`;
}

function PendingBadge() {
  return (
    <span className="ml-2 inline-block rounded bg-[var(--badge-warn-bg)] px-1.5 py-[1px] text-[10px] font-medium text-[var(--badge-warn-fg)]">
      待派工模組接入
    </span>
  );
}

function describeError(e: unknown): string {
  if (e instanceof ApiError) return `${e.errorCode} (${e.status})：${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

export default function DashboardPage() {
  // 日期範圍 — 預設過去 7 日（與舊的 PERIOD = "7d" 行為一致）
  const [range, setRange] = useState<DateRange>(() => getPresetRange("last7"));
  const period = useMemo(() => mapRangeToDashboardPeriod(range), [range]);

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 工單樣本（給 WorkOrderTrendChart 算趨勢 + RecentWorkOrders 顯示前 5）
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [workOrdersHasMore, setWorkOrdersHasMore] = useState(false);
  const [workOrdersLoading, setWorkOrdersLoading] = useState(true);
  const [workOrdersError, setWorkOrdersError] = useState<string | null>(null);

  // 技師樣本（給 TechnicianStatusChart 算分佈）
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [techniciansLoading, setTechniciansLoading] = useState(true);
  const [techniciansError, setTechniciansError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    // 三個並行 fetch（dashboard stats / work-orders / technicians）
    // TODO[E7x §4.3]: 後端 dashboard / work-orders / technicians 尚未支援
    // from/to 自訂範圍 filter；目前先把 range 折回 DashboardPeriod enum，
    // work-orders / technicians 暫不帶日期參數（由前端切片）。
    (async () => {
      setError(null);
      try {
        const data = await api.get<DashboardStats>(
          "/api/v1/dashboard/stats",
          { query: { period } },
        );
        if (!cancelled) setStats(data);
      } catch (e) {
        if (!cancelled) setError(describeError(e));
      }
    })();

    (async () => {
      setWorkOrdersLoading(true);
      setWorkOrdersError(null);
      try {
        const res = await api.get<WorkOrderPage>("/api/v1/work-orders", {
          query: { limit: WORK_ORDERS_LIMIT },
        });
        if (cancelled) return;
        setWorkOrders(res.items ?? []);
        setWorkOrdersHasMore(!!res.has_more);
      } catch (e) {
        if (!cancelled) setWorkOrdersError(describeError(e));
      } finally {
        if (!cancelled) setWorkOrdersLoading(false);
      }
    })();

    (async () => {
      setTechniciansLoading(true);
      setTechniciansError(null);
      try {
        const res = await api.get<TechnicianPage>("/api/v1/technicians", {
          query: { limit: TECHNICIANS_LIMIT },
        });
        if (cancelled) return;
        setTechnicians(res.items ?? []);
      } catch (e) {
        if (!cancelled) setTechniciansError(describeError(e));
      } finally {
        if (!cancelled) setTechniciansLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [period]);

  const conv = stats?.conversations;
  const res = stats?.resolution;
  const recentWorkOrders = useMemo(
    () => workOrders.slice(0, RECENT_WO_DISPLAY),
    [workOrders],
  );

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <Header title="儀表板" subtitle="近 7 日營運概況" />

        <main
          id="main-content"
          tabIndex={-1}
          className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6"
        >
          {/* 動態狀態 — 給 screen reader 知道 fetch 進度（視覺隱藏） */}
          <LiveRegion politeness="polite">
            {workOrdersLoading || techniciansLoading
              ? "正在載入儀表板資料"
              : error || workOrdersError || techniciansError
                ? "資料載入失敗"
                : `儀表板已載入，工單 ${workOrders.length} 筆、技師 ${technicians.length} 位`}
          </LiveRegion>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              載入儀表板失敗：{error}
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-[13px] text-[var(--text-secondary)]">
              統計區間
            </span>
            <DateRangePicker value={range} onChange={setRange} />
          </div>

          <div className="flex gap-6">
            <KpiCard
              title="對話總數（近 7 日）"
              value={conv ? String(conv.total) : "—"}
              subtitle={`進行中 ${conv?.active ?? "—"}・已解決 ${conv?.resolved ?? "—"}`}
              accentColor="#2563EB"
              iconBgColor="#EFF6FF"
              icon={MessageSquare}
            />
            <KpiCard
              title="進行中對話"
              value={conv ? String(conv.active) : "—"}
              subtitle="未結束的對話數"
              accentColor="#2563EB"
              iconBgColor="#EFF6FF"
              icon={Inbox}
            />
            <KpiCard
              title="已解決"
              value={conv ? String(conv.resolved) : "—"}
              valueColor="#10B981"
              subtitle={`AI 解決率 ${formatPercent(res?.ai_resolution_rate)}`}
              accentColor="#10B981"
              iconBgColor="#ECFDF5"
              icon={CheckCircle2}
            />
            <KpiCard
              title="升級至人工"
              value={conv ? String(conv.escalated) : "—"}
              valueColor="#EF4444"
              subtitle="等候客服回覆"
              accentColor="#EF4444"
              iconBgColor="#FEF2F2"
              icon={UserCog}
            />
          </div>

          <div className="flex gap-6">
            <KpiCard
              title="AI 解決率"
              value={formatPercent(res?.ai_resolution_rate)}
              valueColor="#8B5CF6"
              subtitle="案例庫 + RAG 解決占比"
              accentColor="#8B5CF6"
              iconBgColor="#F5F3FF"
              icon={Sparkles}
            />
            <KpiCard
              title="平均解決時間"
              value={formatDuration(res?.avg_resolution_time_seconds)}
              subtitle="從開始到結案"
              accentColor="#2563EB"
              iconBgColor="#EFF6FF"
              icon={Timer}
            />
          </div>

          <HotTopicsCard
            hotTopics={stats?.hot_topics ?? []}
            topBrands={stats?.top_brands ?? []}
          />

          <div>
            <div className="mb-2 flex items-center text-[13px] text-[#71717A]">
              派工管理指標
            </div>
            <div className="flex gap-6">
              <KpiCard
                title="今日工單數"
                value={
                  stats?.work_orders?.today_count != null
                    ? String(stats.work_orders.today_count)
                    : "—"
                }
                subtitle="今日新建立"
                accentColor="#2563EB"
                iconBgColor="#EFF6FF"
                icon={ClipboardList}
              />
              <KpiCard
                title="完工率"
                value={formatPercent(stats?.work_orders?.completion_rate)}
                valueColor="#F59E0B"
                subtitle="今日完工 / 今日新建"
                accentColor="#10B981"
                iconBgColor="#ECFDF5"
                icon={CircleCheckBig}
              />
              <KpiCard
                title="逾時工單"
                value={
                  stats?.work_orders?.overdue_count != null
                    ? String(stats.work_orders.overdue_count)
                    : "—"
                }
                valueColor="#EF4444"
                subtitle="排程時間已過且未結案"
                accentColor="#EF4444"
                iconBgColor="#FEF2F2"
                icon={TriangleAlert}
              />
              <KpiCard
                title="在線技師"
                value={
                  stats?.technicians
                    ? `${stats.technicians.online_count ?? 0} / ${stats.technicians.total_count ?? 0}`
                    : "—"
                }
                subtitle={
                  stats?.technicians?.dispatchable_count != null
                    ? `可派遣 ${stats.technicians.dispatchable_count} 人`
                    : "—"
                }
                accentColor="#F59E0B"
                iconBgColor="#FFFBEB"
                icon={Users}
              />
            </div>
            <div className="mt-4 flex gap-6">
              <div className="flex-1">
                <div className="mb-1 flex items-center text-[12px] text-[#71717A]">
                  <PendingBadge />
                </div>
                <KpiCard
                  title="SLA 達標率"
                  value="88%"
                  subtitle="本月目標 95%"
                  accentColor="#2563EB"
                  iconBgColor="#EFF6FF"
                  icon={Shield}
                  progressBar={{ value: 88, color: "#2563EB" }}
                />
              </div>
            </div>
          </div>

          <div className="flex gap-6">
            <WorkOrderTrendChart
              items={workOrders}
              hasMore={workOrdersHasMore}
              loading={workOrdersLoading}
              error={workOrdersError}
              sampleLimit={WORK_ORDERS_LIMIT}
            />
            <TechnicianStatusChart
              items={technicians}
              loading={techniciansLoading}
              error={techniciansError}
            />
          </div>

          <RecentWorkOrders
            items={recentWorkOrders}
            loading={workOrdersLoading}
            error={workOrdersError}
          />
        </main>
      </div>
    </div>
  );
}
