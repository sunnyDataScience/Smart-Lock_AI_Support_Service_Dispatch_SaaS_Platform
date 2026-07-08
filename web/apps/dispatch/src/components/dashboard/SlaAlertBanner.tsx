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
import RealtimeIndicator from "@shared/components/realtime/RealtimeIndicator";
import { useRealtimeChannel } from "@shared/hooks/useRealtimeChannel";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

type AlertType =
  | "quote_expiring"
  | "dispatch_delay"
  | "response_overdue"
  | "arrival_overdue";

type Severity = "red" | "amber" | "yellow";

interface SlaAlert {
  id: string;
  alert_type: AlertType;
  target_id: string;
  threshold_minutes?: number;
  severity?: Severity;
  escalated_to?: string;
  received_at: string;
}

// Tone（顏色 / icon / href）與 label 分離 — label 由 useTranslations 解析
const TYPE_TONE: Record<
  AlertType,
  {
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
    Icon: Clock,
    bg: "#FEF3C7",
    border: "#FCD34D",
    color: "#92400E",
    href: (id) => `/work-orders/${id}`,
  },
  dispatch_delay: {
    Icon: Zap,
    bg: "#FEE2E2",
    border: "#FCA5A5",
    color: "#991B1B",
    href: (id) => `/admin/dispatch-manual?work_order_id=${id}`,
  },
  response_overdue: {
    Icon: AlertCircle,
    bg: "#FFEDD5",
    border: "#FB923C",
    color: "#9A3412",
    href: (id) => `/work-orders/${id}`,
  },
  arrival_overdue: {
    // F-016 SLA 紅色警報 — Q5=B Soft SLA：dashboard 變紅 + 升 Ops Manager
    // 嚴禁串接賠償 / 自動退款
    Icon: AlertTriangle,
    bg: "#FEE2E2",
    border: "#DC2626",
    color: "#7F1D1D",
    href: (id) => `/admin/work-orders/${id}`,
  },
};

const MAX_ALERTS = 5;

export default function SlaAlertBanner() {
  const t = useTranslations("alerts.sla");
  const tTypes = useTranslations("alerts.sla.types");
  const [alerts, setAlerts] = useState<SlaAlert[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  const { status } = useRealtimeChannel<{
    alert_type?: AlertType;
    target_id?: string;
    threshold_minutes?: number;
    severity?: Severity;
    escalated_to?: string;
  }>({
    channelPath: "/realtime/sla-alerts",
    onMessage: (msg) => {
      const data = (msg.payload ?? msg) as {
        alert_type?: AlertType;
        target_id?: string;
        threshold_minutes?: number;
        severity?: Severity;
        escalated_to?: string;
      };
      if (!data.alert_type || !data.target_id) return;
      setAlerts((prev) => {
        const id = `${data.alert_type}-${data.target_id}-${Date.now()}`;
        const next: SlaAlert = {
          id,
          alert_type: data.alert_type as AlertType,
          target_id: data.target_id as string,
          threshold_minutes: data.threshold_minutes,
          severity: data.severity,
          escalated_to: data.escalated_to,
          received_at: new Date().toISOString(),
        };
        return [next, ...prev].slice(0, MAX_ALERTS);
      });
    },
  });

  const hasRed = alerts.some(
    (a) => a.severity === "red" || a.alert_type === "arrival_overdue",
  );

  function dismiss(id: string) {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  function dismissAll() {
    setAlerts([]);
  }

  if (alerts.length === 0) {
    // 仍顯示一個小型 indicator，讓使用者知道訂閱狀態
    return (
      <div
        data-testid="sla-alert-banner-empty"
        className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-[12px] text-[var(--text-secondary)]"
      >
        <AlertTriangle className="h-4 w-4 text-[#10B981]" />
        <span>{t("channelName")}</span>
        <RealtimeIndicator status={status} />
        <span className="ml-auto text-[var(--text-disabled)]">
          {t("noAlerts")}
        </span>
      </div>
    );
  }

  // 紅色警報（arrival_overdue / severity=red）優先 — F-016
  const headerBorder = hasRed ? "border-red-300" : "border-amber-200";
  const headerBg = hasRed ? "bg-red-50" : "bg-amber-50";
  const headerBorderInner = hasRed ? "border-red-300" : "border-amber-200";
  const headerIconColor = hasRed ? "text-red-700" : "text-amber-700";
  const headerTitleColor = hasRed ? "text-red-900" : "text-amber-900";
  const headerBtnColor = hasRed ? "text-red-800" : "text-amber-800";
  const dividerColor = hasRed ? "divide-red-200" : "divide-amber-200";

  return (
    <section
      data-testid="sla-alert-banner"
      data-severity={hasRed ? "red" : "amber"}
      className={`rounded-lg border ${headerBorder} ${headerBg} shadow-sm`}
    >
      <div
        className={`flex items-center justify-between border-b ${headerBorderInner} px-4 py-2`}
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className={`h-4 w-4 ${headerIconColor}`} />
          <span
            className={`text-[13px] font-semibold ${headerTitleColor}`}
            data-testid="sla-alert-banner-title"
          >
            {hasRed ? t("breached") : t("warning")}
            {t("countSuffix", { count: alerts.length })}
          </span>
          <RealtimeIndicator status={status} compact />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            className={`text-[11px] ${headerBtnColor} hover:underline`}
          >
            {collapsed ? t("expand") : t("collapse")}
          </button>
          <button
            type="button"
            onClick={dismissAll}
            className={`text-[11px] ${headerBtnColor} hover:underline`}
          >
            {t("dismissAll")}
          </button>
        </div>
      </div>
      {!collapsed && (
        <ul className={`divide-y ${dividerColor}`} data-testid="sla-alert-list">
          {alerts.map((a) => {
            const tone = TYPE_TONE[a.alert_type];
            const Icon = tone.Icon;
            return (
              <li
                key={a.id}
                data-testid="sla-alert-item"
                data-alert-type={a.alert_type}
                data-severity={a.severity ?? "amber"}
                className="flex items-start gap-3 px-4 py-3"
                style={{ backgroundColor: tone.bg }}
              >
                <div
                  className="mt-[2px] flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
                  style={{ backgroundColor: "white" }}
                >
                  <Icon className="h-4 w-4" style={{ color: tone.color }} />
                </div>
                <div className="flex flex-1 flex-col">
                  <span
                    className="text-[13px] font-semibold"
                    style={{ color: tone.color }}
                  >
                    {tTypes(`${a.alert_type}.label`)}
                    {a.threshold_minutes != null
                      ? t("thresholdMin", { min: a.threshold_minutes })
                      : ""}
                  </span>
                  <span
                    className="text-[12px]"
                    style={{ color: tone.color, opacity: 0.85 }}
                  >
                    {tTypes(`${a.alert_type}.description`)}
                  </span>
                  <span className="mt-1 font-mono text-[10px] text-[var(--text-disabled)]">
                    {t("targetIdPrefix")}
                    {a.target_id.slice(0, 8)} ·{" "}
                    {new Date(a.received_at).toLocaleTimeString("zh-TW")}
                    {a.escalated_to ? t("escalated", { to: a.escalated_to }) : ""}
                  </span>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1">
                  <Link
                    data-testid="sla-alert-jump"
                    href={tone.href(a.target_id)}
                    className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-[var(--primary)] hover:bg-[#EFF6FF]"
                  >
                    {t("handle")}
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                  <button
                    type="button"
                    onClick={() => dismiss(a.id)}
                    className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-white"
                    aria-label={t("dismissAria")}
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
