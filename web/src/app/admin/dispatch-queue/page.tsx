"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
type DispatchLog = components["schemas"]["DispatchLog"];
type DispatchLogPage = components["schemas"]["DispatchLogPage"];
type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];

const URGENCY_COLOR: Record<NonNullable<WorkOrder["urgency"]>, { bg: string; text: string; label: string }> = {
  high: { bg: "#FEE2E2", text: "#B91C1C", label: "高" },
  medium: { bg: "#FEF3C7", text: "#B45309", label: "中" },
  low: { bg: "#DCFCE7", text: "#15803D", label: "低" },
};

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
  const [logs, setLogs] = useState<DispatchLog[]>([]);
  const [pool, setPool] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [snap, page, poolPage] = await Promise.all([
        api.get<DispatchQueueSnapshot>("/api/v1/work-orders/dispatch-queue"),
        api.get<DispatchLogPage>("/api/v1/dispatch-logs", {
          query: { limit: 50 },
        }),
        api.get<WorkOrderPage>("/api/v1/work-orders/pool"),
      ]);
      setSnapshot(snap);
      const items: DispatchLog[] = page.items ?? [];
      setLogs(items);
      setPool(poolPage.items ?? []);
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
    fetchAll();
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
                onClick={fetchAll}
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
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                可接案件池（listWorkOrderPool）
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                共 {pool.length} 筆 · 依緊急度 + 建立時間排序
              </span>
            </div>
            {pool.length === 0 ? (
              <div className="flex h-20 items-center justify-center text-sm text-[var(--text-secondary)]">
                目前沒有待接工單
              </div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {pool.slice(0, 10).map((wo) => {
                  const urgency = wo.urgency ?? "low";
                  const color = URGENCY_COLOR[urgency];
                  return (
                    <Link
                      key={wo.id}
                      href={`/work-orders/${wo.id}`}
                      className="flex items-center gap-4 px-4 py-3 transition hover:bg-[var(--bg-page)]"
                    >
                      <span className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-secondary)]">
                        #{wo.id.slice(0, 8)}
                      </span>
                      <span
                        className="rounded-md px-2 py-[2px] text-[11px] font-semibold"
                        style={{ backgroundColor: color.bg, color: color.text }}
                      >
                        {color.label}
                      </span>
                      <span className="text-[13px] font-medium text-[var(--text-primary)]">
                        {wo.brand}
                        {wo.model ? ` / ${wo.model}` : ""}
                      </span>
                      <span className="flex-1 truncate text-[12px] text-[var(--text-secondary)]">
                        {wo.district}
                        {wo.address ? ` · ${wo.address}` : ""}
                      </span>
                      <span className="text-[11px] text-[var(--text-disabled)]">
                        {wo.created_at
                          ? new Date(wo.created_at).toLocaleString("zh-TW", {
                              hour12: false,
                            })
                          : "—"}
                      </span>
                    </Link>
                  );
                })}
              </div>
            )}
            {pool.length > 10 && (
              <div className="border-t border-[var(--border)] px-4 py-2 text-center text-[12px] text-[var(--text-secondary)]">
                還有 {pool.length - 10} 筆未顯示，請至 /work-orders 列表處理。
              </div>
            )}
          </div>

          <div className="flex-1 overflow-auto">
            <DispatchQueueTable items={logs} loading={loading} />
          </div>
        </div>
      </div>
    </div>
  );
}
