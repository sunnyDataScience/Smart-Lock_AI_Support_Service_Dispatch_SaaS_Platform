"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  RefreshCw,
  Wallet,
  FileText,
  BarChart3,
  Calendar,
  ChevronDown,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import SettlementTable from "@/components/accounting/SettlementTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Settlement = components["schemas"]["Settlement"];
type SettlementPage = components["schemas"]["SettlementPage"];

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

const segments = [
  { label: "月結(5號)", active: true },
  { label: "雙週結", active: false },
  { label: "週結", active: false },
];

function formatTime(d: Date): string {
  return d.toLocaleTimeString("zh-TW", { hour12: false });
}

export default function AccountingPage() {
  const pathname = usePathname();
  const [items, setItems] = useState<Settlement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const fetchSettlements = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<SettlementPage>(
        "/api/v1/accounting/settlements?limit=50",
      );
      setItems(res.items ?? []);
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
    fetchSettlements();
  }, []);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header + Tabs */}
        <div className="flex flex-col bg-[var(--bg-surface)]">
          {/* Header Row */}
          <div className="flex items-center justify-between px-8 py-5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                財務結算管理
              </h1>
              <button
                onClick={fetchSettlements}
                disabled={loading}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title="重新整理"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
                />
              </button>
              <span className="text-[13px] text-[var(--text-secondary)]">
                {updatedAt
                  ? `最後更新：${formatTime(updatedAt)}`
                  : "尚未載入"}
              </span>
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
                {error ? "連線失敗" : "已連線"}
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

        {/* Settlement Period Selector — disabled until period filter API lands */}
        <div className="flex items-center gap-4 px-8 py-4">
          {/* Month Dropdown — disabled */}
          <button
            disabled
            title="即將推出"
            className="flex cursor-not-allowed items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-page)] px-[14px] py-2 opacity-60"
          >
            <Calendar className="h-4 w-4 text-[var(--text-disabled)]" />
            <span className="text-sm font-medium text-[var(--text-disabled)]">
              所有期間
            </span>
            <ChevronDown className="h-4 w-4 text-[var(--text-disabled)]" />
          </button>

          {/* Segmented Control — disabled */}
          <div
            className="flex rounded-md bg-[#F1F5F9] p-[3px] opacity-60"
            title="即將推出"
          >
            {segments.map((seg) => (
              <button
                key={seg.label}
                disabled
                title="即將推出"
                className={`cursor-not-allowed rounded px-[14px] py-[6px] text-[13px] ${
                  seg.active
                    ? "bg-[var(--bg-surface)] font-semibold text-[var(--text-disabled)] shadow-sm"
                    : "font-medium text-[var(--text-disabled)]"
                }`}
              >
                {seg.label}
              </button>
            ))}
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Total Badge — real count from API */}
          <div className="rounded-lg bg-[var(--primary)] px-5 py-[10px]">
            <span className="text-lg font-bold text-white">
              共 {items.length} 筆
            </span>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mx-8 mb-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Mock Data Notice */}
        <div className="mx-8 mb-2 rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
          列表為 listSettlements 即時資料。期間選擇器、批次確認/標記已付、結算詳情
          modal 待 reconciliation 期間查詢與結算寫入 endpoints 接入後同步上線。
        </div>

        {/* Settlement Table */}
        <div className="flex flex-1 flex-col overflow-auto">
          <SettlementTable items={items} loading={loading} />
        </div>
      </div>
    </div>
  );
}
