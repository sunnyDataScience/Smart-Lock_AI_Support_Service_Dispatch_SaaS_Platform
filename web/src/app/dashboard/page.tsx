"use client";

import { useEffect, useState } from "react";
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
import SlaAlertBanner from "@/components/dashboard/SlaAlertBanner";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type DashboardStats = components["schemas"]["DashboardStats"];

const PERIOD: components["schemas"]["DashboardPeriod"] = "7d";

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
    <span className="ml-2 inline-block rounded bg-[#FEF3C7] px-1.5 py-[1px] text-[10px] font-medium text-[#B45309]">
      待派工模組接入
    </span>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      try {
        const data = await api.get<DashboardStats>(
          "/api/v1/dashboard/stats",
          { query: { period: PERIOD } },
        );
        if (!cancelled) setStats(data);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const conv = stats?.conversations;
  const res = stats?.resolution;

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <Header title="儀表板" subtitle="近 7 日營運概況" />

        <main className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入儀表板失敗：{error}
            </div>
          )}

          <SlaAlertBanner />

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
            <WorkOrderTrendChart />
            <TechnicianStatusChart />
          </div>

          <RecentWorkOrders />
        </main>
      </div>
    </div>
  );
}
