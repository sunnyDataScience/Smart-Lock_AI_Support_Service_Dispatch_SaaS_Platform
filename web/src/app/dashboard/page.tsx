import {
  ClipboardList,
  CircleCheckBig,
  TriangleAlert,
  Users,
  Sparkles,
  Shield,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import KpiCard from "@/components/dashboard/KpiCard";
import WorkOrderTrendChart from "@/components/dashboard/WorkOrderTrendChart";
import TechnicianStatusChart from "@/components/dashboard/TechnicianStatusChart";
import RecentWorkOrders from "@/components/dashboard/RecentWorkOrders";

export default function DashboardPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <Header title="儀表板" subtitle="2026年4月22日 週三" />

        <main className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          <div className="flex gap-6">
            <KpiCard
              title="今日工單數"
              value="47"
              subtitle="vs 昨日 +12%"
              subtitleColor="#10B981"
              accentColor="#2563EB"
              iconBgColor="#EFF6FF"
              icon={ClipboardList}
            />
            <KpiCard
              title="完工率"
              value="86%"
              valueColor="#F59E0B"
              subtitle="vs 昨日 +3%"
              subtitleColor="#10B981"
              accentColor="#10B981"
              iconBgColor="#ECFDF5"
              icon={CircleCheckBig}
            />
            <KpiCard
              title="逾時工單"
              value="3"
              valueColor="#EF4444"
              subtitle="佔總工單 6.4%"
              accentColor="#EF4444"
              iconBgColor="#FEF2F2"
              icon={TriangleAlert}
            />
            <KpiCard
              title="在線技師"
              value="8 / 12"
              subtitle="可派遣 5 人"
              accentColor="#F59E0B"
              iconBgColor="#FFFBEB"
              icon={Users}
            />
          </div>

          <div className="flex gap-6">
            <KpiCard
              title="AI 診斷準確率"
              value="91%"
              valueColor="#10B981"
              subtitle="近 7 日 / 樣本 328 筆"
              accentColor="#8B5CF6"
              iconBgColor="#F5F3FF"
              icon={Sparkles}
            />
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
