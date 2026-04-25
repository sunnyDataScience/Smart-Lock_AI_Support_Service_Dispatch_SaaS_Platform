"use client";

import Link from "next/link";
import { TrendingUp, TrendingDown } from "lucide-react";

interface OrderItem {
  id: string;
  status: string;
  statusBg: string;
  statusText: string;
  customer: string;
  description: string;
  elapsed: string;
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

const activeOrders: OrderItem[] = [
  {
    id: "WO-20260422-0001",
    status: "進行中",
    statusBg: "#DBEAFE",
    statusText: "#1E40AF",
    customer: "陳小姐",
    description: "指紋模組更換",
    elapsed: "已進行 1 小時 30 分鐘",
  },
  {
    id: "WO-20260422-0003",
    status: "已派工",
    statusBg: "#FEF3C7",
    statusText: "#92400E",
    customer: "王先生",
    description: "密碼鎖安裝",
    elapsed: "已進行 25 分鐘",
  },
];

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

export default function TechnicianDetailSidebar() {
  return (
    <aside className="w-[360px] flex-shrink-0 flex flex-col gap-4 bg-[#F1F5F9] p-4 overflow-y-auto h-full">
      <AvailabilityCard />
      <ActiveOrdersCard />
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

function AvailabilityCard() {
  return (
    <CardWrapper>
      <CardTitle>可用狀態</CardTitle>
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

function ActiveOrdersCard() {
  return (
    <CardWrapper>
      <div className="flex items-center gap-2">
        <CardTitle>進行中工單</CardTitle>
        <span
          className="text-xs font-semibold rounded-full px-2 py-0.5 text-white"
          style={{ backgroundColor: "var(--primary)" }}
        >
          {activeOrders.length}
        </span>
      </div>
      <div className="flex flex-col gap-2 w-full">
        {activeOrders.map((order) => (
          <div
            key={order.id}
            className="w-full rounded-lg p-3 flex flex-col gap-1.5"
            style={{ border: "1px solid var(--border)" }}
          >
            <div className="flex items-center justify-between">
              <Link
                href={`/work-orders/${order.id}`}
                className="text-xs font-semibold"
                style={{ color: "var(--primary)" }}
              >
                {order.id}
              </Link>
              <span
                className="text-[11px] font-medium rounded px-1.5 py-0.5"
                style={{
                  backgroundColor: order.statusBg,
                  color: order.statusText,
                }}
              >
                {order.status}
              </span>
            </div>
            <p
              className="text-[13px]"
              style={{ color: "var(--text-primary)" }}
            >
              {order.customer} — {order.description}
            </p>
            <p
              className="text-[11px]"
              style={{ color: "var(--text-disabled)" }}
            >
              {order.elapsed}
            </p>
          </div>
        ))}
      </div>
    </CardWrapper>
  );
}

function CommissionSummaryCard() {
  return (
    <CardWrapper>
      <CardTitle>佣金摘要</CardTitle>
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
      <CardTitle>獎懲紀錄</CardTitle>
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
