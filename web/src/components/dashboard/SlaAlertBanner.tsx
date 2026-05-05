"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  ArrowRight,
  X,
  Zap,
  AlertCircle,
} from "lucide-react";
import RealtimeIndicator from "@/components/realtime/RealtimeIndicator";
import { useRealtimeChannel } from "@/lib/useRealtimeChannel";

type AlertType = "quote_expiring" | "dispatch_delay" | "response_overdue";

interface SlaAlert {
  id: string;
  alert_type: AlertType;
  target_id: string;
  threshold_minutes?: number;
  received_at: string;
}

const TYPE_META: Record<
  AlertType,
  {
    label: string;
    description: string;
    Icon: React.ComponentType<{
      className?: string;
      style?: React.CSSProperties;
    }>;
    bg: string;
    border: string;
    color: string;
    href: (targetId: string) => string;
  }
> = {
  quote_expiring: {
    label: "報價即將過期",
    description: "報價單超過保留時限即將失效",
    Icon: Clock,
    bg: "#FEF3C7",
    border: "#FCD34D",
    color: "#92400E",
    href: (id) => `/work-orders/${id}`,
  },
  dispatch_delay: {
    label: "派工延遲",
    description: "自動派工逾時或連續拒單，需人工介入",
    Icon: Zap,
    bg: "#FEE2E2",
    border: "#FCA5A5",
    color: "#991B1B",
    href: (id) => `/admin/dispatch-manual?work_order_id=${id}`,
  },
  response_overdue: {
    label: "回覆 SLA 違反",
    description: "客戶等待回覆超過 SLA 閾值",
    Icon: AlertCircle,
    bg: "#FFEDD5",
    border: "#FB923C",
    color: "#9A3412",
    href: (id) => `/work-orders/${id}`,
  },
};

const MAX_ALERTS = 5;

export default function SlaAlertBanner() {
  const [alerts, setAlerts] = useState<SlaAlert[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  const { status } = useRealtimeChannel<{
    alert_type?: AlertType;
    target_id?: string;
    threshold_minutes?: number;
  }>({
    channelPath: "/realtime/sla-alerts",
    onMessage: (msg) => {
      const data = (msg.payload ?? msg) as {
        alert_type?: AlertType;
        target_id?: string;
        threshold_minutes?: number;
      };
      if (!data.alert_type || !data.target_id) return;
      setAlerts((prev) => {
        const id = `${data.alert_type}-${data.target_id}-${Date.now()}`;
        const next: SlaAlert = {
          id,
          alert_type: data.alert_type as AlertType,
          target_id: data.target_id as string,
          threshold_minutes: data.threshold_minutes,
          received_at: new Date().toISOString(),
        };
        return [next, ...prev].slice(0, MAX_ALERTS);
      });
    },
  });

  function dismiss(id: string) {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  function dismissAll() {
    setAlerts([]);
  }

  if (alerts.length === 0) {
    // 仍顯示一個小型 indicator，讓使用者知道訂閱狀態
    return (
      <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-[12px] text-[var(--text-secondary)]">
        <AlertTriangle className="h-4 w-4 text-[#10B981]" />
        <span>SLA 告警通道</span>
        <RealtimeIndicator status={status} />
        <span className="ml-auto text-[var(--text-disabled)]">
          目前無告警
        </span>
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 shadow-sm">
      <div className="flex items-center justify-between border-b border-amber-200 px-4 py-2">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-700" />
          <span className="text-[13px] font-semibold text-amber-900">
            SLA 告警（{alerts.length}）
          </span>
          <RealtimeIndicator status={status} compact />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            className="text-[11px] text-amber-800 hover:underline"
          >
            {collapsed ? "展開" : "收合"}
          </button>
          <button
            type="button"
            onClick={dismissAll}
            className="text-[11px] text-amber-800 hover:underline"
          >
            全部已讀
          </button>
        </div>
      </div>
      {!collapsed && (
        <ul className="divide-y divide-amber-200">
          {alerts.map((a) => {
            const meta = TYPE_META[a.alert_type];
            const Icon = meta.Icon;
            return (
              <li
                key={a.id}
                className="flex items-start gap-3 px-4 py-3"
                style={{ backgroundColor: meta.bg }}
              >
                <div
                  className="mt-[2px] flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
                  style={{ backgroundColor: "white" }}
                >
                  <Icon className="h-4 w-4" style={{ color: meta.color }} />
                </div>
                <div className="flex flex-1 flex-col">
                  <span
                    className="text-[13px] font-semibold"
                    style={{ color: meta.color }}
                  >
                    {meta.label}
                    {a.threshold_minutes != null
                      ? `（閾值 ${a.threshold_minutes} 分）`
                      : ""}
                  </span>
                  <span
                    className="text-[12px]"
                    style={{ color: meta.color, opacity: 0.85 }}
                  >
                    {meta.description}
                  </span>
                  <span className="mt-1 font-mono text-[10px] text-[var(--text-disabled)]">
                    target #{a.target_id.slice(0, 8)} ·{" "}
                    {new Date(a.received_at).toLocaleTimeString("zh-TW")}
                  </span>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1">
                  <Link
                    href={meta.href(a.target_id)}
                    className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-[var(--primary)] hover:bg-[#EFF6FF]"
                  >
                    處理
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                  <button
                    type="button"
                    onClick={() => dismiss(a.id)}
                    className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-white"
                    aria-label="忽略"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
