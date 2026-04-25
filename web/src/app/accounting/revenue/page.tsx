"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  Clock3,
  DollarSign,
  Calculator,
  CircleCheck,
  TriangleAlert,
  TrendingUp,
  Calendar,
  Download,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import RevenueTrendChart from "@/components/accounting/RevenueTrendChart";
import BrandRevenueChart from "@/components/accounting/BrandRevenueChart";
import ServiceTypeChart from "@/components/accounting/ServiceTypeChart";

const tabs = [
  {
    icon: Wallet,
    label: "結算管理",
    href: "/accounting" as string | undefined,
    dot: false,
  },
  {
    icon: FileText,
    label: "發票管理",
    href: "/accounting/invoices" as string | undefined,
    dot: true,
  },
  {
    icon: BarChart3,
    label: "營收報表",
    href: "/accounting/revenue" as string | undefined,
    dot: false,
  },
];

const kpiCards = [
  {
    icon: DollarSign,
    iconColor: "#2563EB",
    iconBg: "#DBEAFE",
    title: "本月營收",
    value: "NT$ 1,284,500",
    trend: "+12.3%",
    trendColor: "#10B981",
  },
  {
    icon: Calculator,
    iconColor: "#10B981",
    iconBg: "#D1FAE5",
    title: "平均工單金額",
    value: "NT$ 3,850",
    trend: "+5.2%",
    trendColor: "#10B981",
  },
  {
    icon: CircleCheck,
    iconColor: "#10B981",
    iconBg: "#D1FAE5",
    title: "付款成功率",
    value: "96.8%",
    trend: "+1.2%",
    trendColor: "#10B981",
  },
  {
    icon: TriangleAlert,
    iconColor: "#F59E0B",
    iconBg: "#FEF3C7",
    title: "未收帳款",
    value: "NT$ 128,400",
    sub: "共 34 筆未收",
    subColor: "#F59E0B",
  },
];

const segments = [
  { label: "日", active: false },
  { label: "週", active: false },
  { label: "月", active: true },
];

export default function RevenuePage() {
  const pathname = usePathname();

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          {/* Header Row */}
          <div className="flex items-center justify-between px-8 pt-4 pb-3">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                財務結算管理
              </h1>
              <RefreshCw className="h-5 w-5 text-[var(--text-secondary)]" />
            </div>
            <div className="flex items-center gap-[6px]">
              <Clock3 className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                最後更新：2026/04/22 14:30
              </span>
            </div>
          </div>

          {/* Tab Bar */}
          <div className="flex border-b border-[var(--border)] px-8">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const content = (
                <>
                  <tab.icon
                    className={`h-[18px] w-[18px] ${
                      isActive
                        ? "text-[var(--primary)]"
                        : "text-[var(--text-secondary)]"
                    }`}
                  />
                  <span
                    className={`text-sm ${
                      isActive
                        ? "font-semibold text-[var(--primary)]"
                        : "font-medium text-[var(--text-secondary)]"
                    }`}
                  >
                    {tab.label}
                  </span>
                  {tab.dot && (
                    <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
                  )}
                </>
              );

              const className = `flex items-center gap-2 px-4 py-3 ${
                isActive ? "border-b-2 border-[var(--primary)]" : ""
              }`;

              if (tab.href) {
                return (
                  <Link key={tab.label} href={tab.href} className={className}>
                    {content}
                  </Link>
                );
              }

              return (
                <div key={tab.label} className={className}>
                  {content}
                </div>
              );
            })}
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex flex-1 flex-col overflow-auto">
          {/* KPI Cards */}
          <div className="flex gap-4 px-8 py-5">
            {kpiCards.map((card) => (
              <div
                key={card.title}
                className="flex flex-1 items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
              >
                <div
                  className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl"
                  style={{ backgroundColor: card.iconBg }}
                >
                  <card.icon
                    className="h-6 w-6"
                    style={{ color: card.iconColor }}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                    {card.title}
                  </span>
                  <span className="text-[22px] font-bold text-[var(--text-primary)]">
                    {card.value}
                  </span>
                  {card.trend && (
                    <div className="flex items-center gap-1">
                      <TrendingUp
                        className="h-[14px] w-[14px]"
                        style={{ color: card.trendColor }}
                      />
                      <span
                        className="text-[13px] font-semibold"
                        style={{ color: card.trendColor }}
                      >
                        {card.trend}
                      </span>
                    </div>
                  )}
                  {card.sub && (
                    <span
                      className="text-[13px] font-medium"
                      style={{ color: card.subColor }}
                    >
                      {card.sub}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Controls Row */}
          <div className="flex items-center justify-between px-8">
            <div className="flex items-center gap-4">
              {/* Segmented Control */}
              <div className="flex rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                {segments.map((seg) => (
                  <button
                    key={seg.label}
                    className={`rounded-md px-4 py-2 text-[13px] ${
                      seg.active
                        ? "bg-[var(--primary)] font-semibold text-white"
                        : "font-medium text-[var(--text-secondary)]"
                    }`}
                  >
                    {seg.label}
                  </button>
                ))}
              </div>

              {/* Date Range */}
              <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
                <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
                <span className="text-[13px] text-[var(--text-primary)]">
                  2026/01/01 - 2026/04/22
                </span>
              </button>
            </div>
          </div>

          {/* Main Chart */}
          <div className="px-8 pt-4">
            <RevenueTrendChart />
          </div>

          {/* Bottom Charts Row */}
          <div className="flex gap-4 px-8 py-4" style={{ minHeight: 320 }}>
            <BrandRevenueChart />
            <ServiceTypeChart />
          </div>

          {/* Export Controls */}
          <div className="flex items-center justify-end gap-3 px-8 py-3">
            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-[10px]">
              <Download className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-sm font-medium text-[var(--text-primary)]">
                CSV匯出
              </span>
            </button>
            <button className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-[10px]">
              <Download className="h-4 w-4 text-white" />
              <span className="text-sm font-medium text-white">Excel匯出</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
