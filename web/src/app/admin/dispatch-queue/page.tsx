"use client";

import { useState } from "react";
import {
  OctagonAlert,
  RotateCw,
  TriangleAlert,
  Timer,
  Search,
  ChevronDown,
  RefreshCw,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import DispatchQueueTable from "@/components/dispatch-queue/DispatchQueueTable";

interface StatCard {
  title: string;
  value: number;
  subtitle: string;
  borderColor: string;
  iconColor: string;
  icon: React.ElementType;
}

const statCards: StatCard[] = [
  {
    title: "卡關工單",
    value: 3,
    subtitle: "需立即介入",
    borderColor: "#EF4444",
    iconColor: "#EF4444",
    icon: OctagonAlert,
  },
  {
    title: "第 2 次派工",
    value: 7,
    subtitle: "已重派一次",
    borderColor: "#F59E0B",
    iconColor: "#F59E0B",
    icon: RotateCw,
  },
  {
    title: "第 3 次派工",
    value: 2,
    subtitle: "最後一次嘗試中",
    borderColor: "#F97316",
    iconColor: "#F97316",
    icon: TriangleAlert,
  },
  {
    title: "逾時未接",
    value: 1,
    subtitle: "15 分鐘未回應",
    borderColor: "#DC2626",
    iconColor: "#DC2626",
    icon: Timer,
  },
];

export default function DispatchQueuePage() {
  const [urgentOnly, setUrgentOnly] = useState(false);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-6 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-[13px] text-[var(--text-secondary)]">
                首頁 &gt; 派工管理 &gt; 派工佇列
              </span>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                  派工佇列監控
                </h1>
                <span className="flex items-center gap-[6px] rounded-full bg-[#DCFCE7] px-3 py-1 text-xs font-medium text-[#15803D]">
                  <span className="h-[6px] w-[6px] rounded-full bg-[#22C55E]" />
                  即時連線中
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-[var(--text-secondary)]">
                最後更新：14:02:06
              </span>
              <button className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)]">
                <RefreshCw className="h-4 w-4 text-[var(--text-secondary)]" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4">
            {statCards.map((card) => (
              <button
                key={card.title}
                className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5 text-left transition-shadow hover:-translate-y-[2px] hover:shadow-md"
                style={{ borderLeftWidth: 4, borderLeftColor: card.borderColor }}
              >
                <card.icon
                  className="h-6 w-6 shrink-0"
                  style={{ color: card.iconColor }}
                />
                <div className="flex flex-col gap-[2px]">
                  <span className="text-xs font-medium text-[var(--text-secondary)]">
                    {card.title}
                  </span>
                  <span className="text-3xl font-bold text-[var(--text-primary)]">
                    {card.value}
                  </span>
                  <span className="text-xs text-[var(--text-disabled)]">
                    {card.subtitle}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
            <Search className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="搜尋工單編號、客戶、地址..."
              className="h-9 flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]">
            派工次數：全部
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
          </button>

          <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]">
            回應狀態：全部
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
          </button>

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
            <span className="text-sm text-[var(--text-primary)]">
              僅顯示需介入
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-auto px-8 py-5">
          <DispatchQueueTable />
        </div>
      </div>
    </div>
  );
}
