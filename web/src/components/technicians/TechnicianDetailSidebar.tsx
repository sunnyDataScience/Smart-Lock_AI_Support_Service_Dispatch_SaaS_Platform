"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import {
  STATUS_GROUP_MAP,
  STATUS_GROUP_STYLE,
} from "@/components/work-orders/WorkOrdersTable";
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
  label: string;
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
  { label: "一般維修佣金 (70%)", value: "NT$ 28,000" },
  { label: "安裝佣金 (60%)", value: "NT$ 12,000" },
  { label: "客供材料佣金 (80%)", value: "NT$ 4,800" },
  { label: "獎金加項", value: "+NT$ 1,200", color: "#059669", bold: true },
  {
    label: "扣款減項",
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
  return (
    <span
      className="text-[10px] font-medium rounded px-1.5 py-0.5"
      style={{ backgroundColor: "#F1F5F9", color: "var(--text-disabled)" }}
      title="示意資料，待相關模組接入後顯示真實內容"
    >
      示意
    </span>
  );
}

function AvailabilityCard() {
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>可用狀態</CardTitle>
        <MockBadge />
      </div>
      <div className="flex items-center justify-between w-full">
        <div className="flex items-center gap-2.5">
          <span
            className="w-3.5 h-3.5 rounded-full"
            style={{ backgroundColor: "#059669" }}
          />
          <span className="text-sm font-semibold" style={{ color: "#059669" }}>
            可用
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
        最後上線：5 分鐘前
      </p>
      <p className="text-[11px]" style={{ color: "var(--text-disabled)" }}>
        系統將在無回應 30 分鐘後自動切為離線
      </p>
    </CardWrapper>
  );
}

function ActiveOrdersCard({ technicianId }: { technicianId?: string }) {
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
        <CardTitle>進行中工單</CardTitle>
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
          載入失敗：{error}
        </span>
      )}

      {!error && loading && orders.length === 0 && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          查詢中…
        </span>
      )}

      {!error && !loading && orders.length === 0 && (
        <span className="text-xs" style={{ color: "var(--text-disabled)" }}>
          目前無進行中工單
        </span>
      )}

      {orders.length > 0 && (
        <div className="flex flex-col gap-2 w-full">
          {orders.map((order) => {
            const group = STATUS_GROUP_MAP[order.status];
            const style = STATUS_GROUP_STYLE[group];
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
                    style={{ backgroundColor: style.bg, color: style.color }}
                  >
                    {style.label}
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
                  建立於 {formatRelative(order.created_at)}
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
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>佣金摘要</CardTitle>
        <MockBadge />
      </div>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        2026年4月
      </p>
      <p className="text-[28px] font-bold" style={{ color: "#059669" }}>
        NT$ 45,600
      </p>
      <div className="flex flex-col gap-1.5 w-full">
        {commissionRows.map((row) => (
          <div key={row.label} className="flex items-center justify-between w-full">
            <span
              className="text-xs"
              style={{ color: "var(--text-secondary)" }}
            >
              {row.label}
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
          待結算
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
          月結 (5號)
        </span>
        <span
          className="text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          下次結算：2026/05/05
        </span>
      </div>
    </CardWrapper>
  );
}

function PenaltyBonusLog() {
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>獎懲紀錄</CardTitle>
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
        查看完整紀錄 →
      </Link>
    </CardWrapper>
  );
}
