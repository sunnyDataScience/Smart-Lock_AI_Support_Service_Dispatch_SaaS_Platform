"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_TONE,
  type StatusGroup,
} from "@/components/work-orders/WorkOrdersTable";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type WorkOrder = components["schemas"]["WorkOrder"];
type WorkOrderPage = components["schemas"]["WorkOrderPage"];
type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

const ACTIVE_STATUSES: ReadonlySet<WorkOrderStatus> = new Set([
  "accepted",
  "scheduled",
  "dispatching",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
]);

interface Props {
  technicianId?: string;
}

interface CommissionRow {
  labelKey: "repair" | "install" | "customMaterial" | "bonus" | "penalty";
  value: string;
  color?: string;
  bold?: boolean;
}

interface LogEntry {
  type: "bonus" | "penalty";
  title: string;
  date: string;
  amount: string;
}

const commissionRows: CommissionRow[] = [
  { labelKey: "repair", value: "NT$ 28,000" },
  { labelKey: "install", value: "NT$ 12,000" },
  { labelKey: "customMaterial", value: "NT$ 4,800" },
  { labelKey: "bonus", value: "+NT$ 1,200", color: "#059669", bold: true },
  {
    labelKey: "penalty",
    value: "-NT$ 400",
    color: "var(--error)",
    bold: true,
  },
];

const logEntries: LogEntry[] = [
  { type: "bonus", title: "高評價獎金 (5星)", date: "2026-04-21", amount: "+NT$ 200" },
  { type: "bonus", title: "準時完工獎金", date: "2026-04-20", amount: "+NT$ 150" },
  { type: "penalty", title: "遲到扣款 (逾時15分鐘)", date: "2026-04-18", amount: "-NT$ 200" },
  { type: "bonus", title: "客戶推薦獎金", date: "2026-04-15", amount: "+NT$ 500" },
];

export default function TechnicianDetailSidebar({ technicianId }: Props) {
  return (
    <aside className="w-[360px] flex-shrink-0 flex flex-col gap-4 bg-[#F1F5F9] p-4 overflow-y-auto h-full">
      <AvailabilityCard />
      <ActiveOrdersCard technicianId={technicianId} />
      <CommissionSummaryCard />
      <PenaltyBonusLog />
    </aside>
  );
}

function CardWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="w-full rounded-xl p-4 flex flex-col gap-3"
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 1px 4px rgba(15, 23, 42, 0.05)",
      }}
    >
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="text-base font-semibold"
      style={{ color: "var(--text-primary)" }}
    >
      {children}
    </h3>
  );
}

function MockBadge() {
  const t = useTranslations("components.technicians.detailSidebar");
  return (
    <span
      className="text-[10px] font-medium rounded px-1.5 py-0.5"
      style={{ backgroundColor: "#F1F5F9", color: "var(--text-disabled)" }}
      title={t("mockTooltip")}
    >
      {t("mockLabel")}
    </span>
  );
}

function AvailabilityCard() {
  const t = useTranslations("components.technicians.detailSidebar");
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>{t("availabilityTitle")}</CardTitle>
        <MockBadge />
      </div>
      <div className="flex items-center justify-between w-full">
        <div className="flex items-center gap-2.5">
          <span
            className="w-3.5 h-3.5 rounded-full"
            style={{ backgroundColor: "#059669" }}
          />
          <span className="text-sm font-semibold" style={{ color: "#059669" }}>
            {t("availabilityOnline")}
          </span>
        </div>
        <div
          className="relative w-[44px] h-[24px] rounded-full"
          style={{ backgroundColor: "var(--success)" }}
        >
          <span className="absolute right-1 top-1 w-4 h-4 rounded-full bg-white shadow-sm" />
        </div>
      </div>
      <p className="text-xs" style={{ color: "var(--text-disabled)" }}>
        {t("lastOnline")}
      </p>
      <p className="text-[11px]" style={{ color: "var(--text-disabled)" }}>
        {t("autoOffline")}
      </p>
    </CardWrapper>
  );
}

function ActiveOrdersCard({ technicianId }: { technicianId?: string }) {
  const t = useTranslations("components.technicians.detailSidebar");
  const tGroup = useTranslations("status.workOrderGroup");

  const groupLabels: Record<StatusGroup, string> = useMemo(
    () => ({
      pending: tGroup("pending"),
      dispatched: tGroup("dispatched"),
      in_progress: tGroup("in_progress"),
      done: tGroup("done"),
      cancelled: tGroup("cancelled"),
    }),
    [tGroup],
  );

  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!technicianId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setOrders([]);
    (async () => {
      try {
        const res = await api.get<WorkOrderPage>("/api/v1/work-orders", {
          query: { technician_id: technicianId, limit: 20 },
        });
        if (cancelled) return;
        const items = (res.items ?? []) as WorkOrder[];
        setOrders(items.filter((o) => ACTIVE_STATUSES.has(o.status)));
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [technicianId]);

  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>{t("activeOrdersTitle")}</CardTitle>
        {orders.length > 0 && (
          <span
            className="text-xs font-semibold rounded-full px-2 py-0.5 text-white"
            style={{ backgroundColor: "var(--primary)" }}
          >
            {orders.length}
          </span>
        )}
      </div>

      {error && (
        <span className="text-[12px]" style={{ color: "var(--error)" }}>
          {t("loadFailed", { error })}
        </span>
      )}

      {!error && loading && orders.length === 0 && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          {t("querying")}
        </span>
      )}

      {!error && !loading && orders.length === 0 && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          {t("noActive")}
        </span>
      )}

      {orders.length > 0 && (
        <div className="flex flex-col gap-2 w-full">
          {orders.map((order) => {
            const group = STATUS_GROUP_MAP[order.status];
            const tone = STATUS_GROUP_TONE[group];
            const shortId = order.id.slice(0, 8);
            const device = [order.brand, order.model].filter(Boolean).join(" ") || "—";
            const location = order.district || order.address || "—";
            return (
              <div
                key={order.id}
                className="w-full rounded-lg p-3 flex flex-col gap-1.5"
                style={{ border: "1px solid var(--border)" }}
              >
                <div className="flex items-center justify-between">
                  <Link
                    href={`/work-orders/${order.id}`}
                    className="font-mono text-xs font-semibold hover:underline"
                    style={{ color: "var(--primary)" }}
                    title={order.id}
                  >
                    {shortId}
                  </Link>
                  <span
                    className="text-[11px] font-medium rounded px-1.5 py-0.5"
                    style={{ backgroundColor: tone.bg, color: tone.color }}
                  >
                    {groupLabels[group]}
                  </span>
                </div>
                <p
                  className="text-[13px]"
                  style={{ color: "var(--text-primary)" }}
                >
                  {device} — {location}
                </p>
                <p
                  className="text-[11px]"
                  style={{ color: "var(--text-disabled)" }}
                >
                  {t("createdAt", { time: formatRelative(order.created_at) })}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </CardWrapper>
  );
}

function CommissionSummaryCard() {
  const t = useTranslations("components.technicians.detailSidebar");
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>{t("commissionTitle")}</CardTitle>
        <MockBadge />
      </div>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        {t("commissionPeriod")}
      </p>
      <p className="text-[28px] font-bold" style={{ color: "#059669" }}>
        NT$ 45,600
      </p>
      <div className="flex flex-col gap-1.5 w-full">
        {commissionRows.map((row) => (
          <div key={row.labelKey} className="flex items-center justify-between w-full">
            <span
              className="text-xs"
              style={{ color: "var(--text-secondary)" }}
            >
              {t(`commissionRow.${row.labelKey}`)}
            </span>
            <span
              className="text-xs"
              style={{
                color: row.color ?? "var(--text-primary)",
                fontWeight: row.bold ? 600 : 400,
              }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
      <div
        className="w-full h-px"
        style={{ backgroundColor: "var(--border)" }}
      />
      <div className="flex items-center justify-between w-full">
        <span
          className="text-[13px] font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          {t("pending")}
        </span>
        <span className="text-sm font-semibold" style={{ color: "#D97706" }}>
          NT$ 12,400
        </span>
      </div>
      <div className="flex items-center gap-2 w-full">
        <span
          className="text-[11px] font-medium rounded px-2 py-0.5"
          style={{ backgroundColor: "#DBEAFE", color: "#1E40AF" }}
        >
          {t("monthlyBadge")}
        </span>
        <span
          className="text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          {t("nextSettle")}
        </span>
      </div>
    </CardWrapper>
  );
}

function PenaltyBonusLog() {
  const t = useTranslations("components.technicians.detailSidebar");
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>{t("logTitle")}</CardTitle>
        <MockBadge />
      </div>
      <div className="flex flex-col gap-2.5 w-full">
        {logEntries.map((entry, i) => {
          const isBonus = entry.type === "bonus";
          return (
            <div key={i} className="flex items-center gap-2 w-full">
              <span
                className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
                style={{
                  backgroundColor: isBonus ? "#D1FAE5" : "#FEE2E2",
                  color: isBonus ? "#059669" : "var(--error)",
                }}
              >
                {isBonus ? (
                  <TrendingUp size={14} />
                ) : (
                  <TrendingDown size={14} />
                )}
              </span>
              <div className="flex-1 min-w-0">
                <p
                  className="text-xs font-medium truncate"
                  style={{ color: "var(--text-primary)" }}
                >
                  {entry.title}
                </p>
                <p
                  className="text-[11px]"
                  style={{ color: "var(--text-disabled)" }}
                >
                  {entry.date}
                </p>
              </div>
              <span
                className="text-xs font-semibold flex-shrink-0"
                style={{
                  color: isBonus ? "#059669" : "var(--error)",
                }}
              >
                {entry.amount}
              </span>
            </div>
          );
        })}
      </div>
      <Link
        href="#"
        className="text-[13px]"
        style={{ color: "var(--primary)" }}
      >
        {t("viewLogAll")}
      </Link>
    </CardWrapper>
  );
}
