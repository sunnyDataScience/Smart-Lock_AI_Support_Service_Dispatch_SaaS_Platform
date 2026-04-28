"use client";

import { useEffect, useState } from "react";
import {
  CircleDashed,
  Send,
  CircleCheck,
  Timer,
  Search,
  ChevronDown,
  RefreshCw,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import DispatchQueueTable from "@/components/dispatch-queue/DispatchQueueTable";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/types/api.generated";

type DispatchQueueSnapshot = components["schemas"]["DispatchQueueSnapshot"];

interface CardConfig {
  key: keyof DispatchQueueSnapshot;
  title: string;
  subtitle: string;
  borderColor: string;
  iconColor: string;
  icon: React.ElementType;
}

const cardConfigs: CardConfig[] = [
  {
    key: "pending",
    title: "待派工",
    subtitle: "尚未指派技師",
    borderColor: "#F59E0B",
    iconColor: "#F59E0B",
    icon: CircleDashed,
  },
  {
    key: "assigning",
    title: "派工中",
    subtitle: "等待技師回應",
    borderColor: "#3B82F6",
    iconColor: "#3B82F6",
    icon: Send,
  },
  {
    key: "assigned",
    title: "已派工",
    subtitle: "技師已接受",
    borderColor: "#10B981",
    iconColor: "#10B981",
    icon: CircleCheck,
  },
  {
    key: "sla_at_risk",
    title: "SLA 風險",
    subtitle: "2 小時內可能逾期",
    borderColor: "#EF4444",
    iconColor: "#EF4444",
    icon: Timer,
  },
];

function formatTime(d: Date): string {
  return d.toLocaleTimeString("zh-TW", { hour12: false });
}

export default function DispatchQueuePage() {
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [snapshot, setSnapshot] = useState<DispatchQueueSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const fetchSnapshot = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<DispatchQueueSnapshot>(
        "/api/v1/work-orders/dispatch-queue",
      );
      setSnapshot(res);
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
    fetchSnapshot();
  }, []);

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
            <div className="flex items-center gap-3">
              <span className="text-sm text-[var(--text-secondary)]">
                {updatedAt
                  ? `最後更新：${formatTime(updatedAt)}`
                  : "尚未載入"}
              </span>
              <button
                onClick={fetchSnapshot}
                disabled={loading}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                title="重新整理"
              >
                <RefreshCw
                  className={`h-4 w-4 text-[var(--text-secondary)] ${loading ? "animate-spin" : ""}`}
                />
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="grid grid-cols-4 gap-4">
            {cardConfigs.map((card) => {
              const value = snapshot?.[card.key];
              const display =
                loading && snapshot === null
                  ? "—"
                  : value != null
                    ? String(value)
                    : "—";
              return (
                <div
                  key={card.key}
                  className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-5"
                  style={{
                    borderLeftWidth: 4,
                    borderLeftColor: card.borderColor,
                  }}
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
                      {display}
                    </span>
                    <span className="text-xs text-[var(--text-disabled)]">
                      {card.subtitle}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-3">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 opacity-60">
            <Search className="h-[18px] w-[18px] text-[var(--text-disabled)]" />
            <input
              type="text"
              disabled
              placeholder="即將推出：搜尋工單編號、客戶、地址"
              className="h-9 flex-1 cursor-not-allowed bg-transparent text-sm text-[var(--text-disabled)] outline-none placeholder:text-[var(--text-disabled)]"
              title="即將推出"
            />
          </div>

          <button
            disabled
            title="即將推出"
            className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-disabled)] opacity-60"
          >
            派工次數：全部
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
          </button>

          <button
            disabled
            title="即將推出"
            className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-page)] px-3 py-2 text-sm text-[var(--text-disabled)] opacity-60"
          >
            回應狀態：全部
            <ChevronDown className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
          </button>

          <div
            className="flex items-center gap-2 opacity-60"
            title="即將推出"
          >
            <button
              disabled
              onClick={() => setUrgentOnly((prev) => !prev)}
              className={`relative h-5 w-9 cursor-not-allowed rounded-full transition-colors ${
                urgentOnly ? "bg-[var(--primary)]" : "bg-[#CBD5E1]"
              }`}
            >
              <span
                className={`absolute top-[2px] h-4 w-4 rounded-full bg-white transition-transform ${
                  urgentOnly ? "left-[18px]" : "left-[2px]"
                }`}
              />
            </button>
            <span className="text-sm text-[var(--text-disabled)]">
              僅顯示需介入
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-4 px-8 py-5">
          <div className="rounded-lg border border-[var(--border)] bg-[#FFFBEB] px-4 py-3 text-[13px] leading-relaxed text-[#92400E]">
            佇列明細表格目前為示意資料。即時 WebSocket
            (/realtime/dispatch-queue) 與 listDispatchCandidates / assignDispatch
            等寫入 endpoints 待派工 AI 推薦引擎接入後同步上線；上方四張卡為
            getDispatchQueue 即時聚合的真實數字。
          </div>
          <div className="flex-1 overflow-auto">
            <DispatchQueueTable />
          </div>
        </div>
      </div>
    </div>
  );
}
