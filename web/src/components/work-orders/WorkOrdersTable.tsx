"use client";

import Link from "next/link";

interface WorkOrder {
  id: string;
  customer: string;
  address: string;
  brand: string;
  status: { label: string; color: string; bg: string; border?: string };
  technician: { name: string; color: string } | null;
  sla: { text: string; color?: string; bold?: boolean };
  time: string;
  selected?: boolean;
}

const orders: WorkOrder[] = [
  {
    id: "WO-20260422-0001",
    customer: "陳小姐",
    address: "台北市大安區...",
    brand: "Yale YDM-4109",
    status: { label: "已建立", color: "#6366F1", bg: "#EEF2FF" },
    technician: null,
    sla: { text: "剩餘 02:45" },
    time: "2026-04-22 14:23",
  },
  {
    id: "WO-20260422-0002",
    customer: "王大明",
    address: "新北市板橋區...",
    brand: "Samsung DP609",
    status: { label: "已派工", color: "#8B5CF6", bg: "#F5F3FF" },
    technician: { name: "李技師", color: "#C4B5FD" },
    sla: { text: "剩餘 01:30" },
    time: "2026-04-22 14:15",
  },
  {
    id: "WO-20260422-0003",
    customer: "林美華",
    address: "台中市西屯區...",
    brand: "Gateman F300",
    status: { label: "進行中", color: "#3B82F6", bg: "#DBEAFE", border: "#3B82F6" },
    technician: { name: "張師傅", color: "#93C5FD" },
    sla: { text: "剩餘 04:20" },
    time: "2026-04-22 13:45",
    selected: true,
  },
  {
    id: "WO-20260421-0015",
    customer: "黃志明",
    address: "高雄市左營區...",
    brand: "美樂 ENTR",
    status: { label: "延遲中", color: "#F59E0B", bg: "#FEF3C7" },
    technician: { name: "謬師傅", color: "#FCD34D" },
    sla: { text: "剩餘 00:25", color: "#F59E0B", bold: true },
    time: "04-21 09:30",
  },
  {
    id: "WO-20260421-0012",
    customer: "劉家豪",
    address: "台北市信義區...",
    brand: "Philips 9300",
    status: { label: "逾時", color: "#EF4444", bg: "#FEE2E2" },
    technician: { name: "吳技師", color: "#FCA5A5" },
    sla: { text: "逾時 01:15", color: "#EF4444", bold: true },
    time: "04-21 08:00",
  },
  {
    id: "WO-20260420-0008",
    customer: "趙雅婷",
    address: "桃園市中壢區...",
    brand: "Yale YDR-323",
    status: { label: "已完工", color: "#10B981", bg: "#D1FAE5" },
    technician: { name: "陳師傅", color: "#6EE7B7" },
    sla: { text: "--", color: "var(--text-disabled)" },
    time: "04-20 16:00",
  },
  {
    id: "WO-20260420-0005",
    customer: "周建國",
    address: "新竹市東區...",
    brand: "Samsung DR708",
    status: { label: "返工中", color: "#EF4444", bg: "#FEE2E2" },
    technician: { name: "李技師", color: "#C4B5FD" },
    sla: { text: "剩餘 03:00" },
    time: "04-20 11:30",
  },
  {
    id: "WO-20260419-0022",
    customer: "吳淑芬",
    address: "台北市中山區...",
    brand: "Gateman V20",
    status: { label: "已取消", color: "#EF4444", bg: "#FEE2E2" },
    technician: null,
    sla: { text: "--", color: "var(--text-disabled)" },
    time: "04-19 10:00",
  },
];

const columns = [
  { label: "", width: "w-[40px]", center: true },
  { label: "工單編號", width: "w-[160px]", center: false },
  { label: "客戶姓名", width: "w-[80px]", center: false },
  { label: "地址", width: "w-[150px]", center: false },
  { label: "品牌/型號", width: "w-[120px]", center: false },
  { label: "狀態", width: "w-[80px]", center: false },
  { label: "指派技師", width: "w-[90px]", center: false },
  { label: "SLA倒數", width: "w-[100px]", center: false },
  { label: "建立時間", width: "w-[110px]", center: false },
  { label: "操作", width: "w-[50px]", center: true },
];

export default function WorkOrdersTable() {
  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-sm">
      {/* Header */}
      <div className="flex h-[44px] items-center bg-[#F8FAFC] px-4">
        <div className="flex w-[40px] items-center justify-center">
          <div className="h-4 w-4 rounded-[3px] border-[1.5px] border-[var(--border)]" />
        </div>
        {columns.slice(1).map((col) => (
          <div
            key={col.label}
            className={`flex items-center ${col.width} ${col.center ? "justify-center" : ""}`}
          >
            <span className="text-[12px] font-semibold text-[#64748B]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      <div className="h-px w-full bg-[var(--border)]" />

      {/* Rows */}
      {orders.map((order, idx) => (
        <div key={order.id}>
          <div
            className={`flex h-12 items-center px-4 ${
              order.selected
                ? "bg-[#DBEAFE]"
                : idx % 2 === 0
                  ? "bg-white"
                  : "bg-[#F8FAFC]"
            }`}
          >
            {/* Checkbox */}
            <div className="flex w-[40px] items-center justify-center">
              {order.selected ? (
                <div className="flex h-4 w-4 items-center justify-center rounded-[3px] bg-[var(--primary)]">
                  <span className="text-[10px] font-bold text-white">✓</span>
                </div>
              ) : (
                <div className="h-4 w-4 rounded-[3px] border-[1.5px] border-[var(--border)]" />
              )}
            </div>

            {/* 工單編號 */}
            <div className="flex w-[160px] items-center">
              <Link
                href={`/work-orders/${order.id}`}
                className="font-mono text-[12px] font-medium text-[var(--primary)] hover:underline"
              >
                {order.id}
              </Link>
            </div>

            {/* 客戶姓名 */}
            <div className="flex w-[80px] items-center">
              <span className="text-[13px] text-[var(--text-primary)]">
                {order.customer}
              </span>
            </div>

            {/* 地址 */}
            <div className="flex w-[150px] items-center">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {order.address}
              </span>
            </div>

            {/* 品牌/型號 */}
            <div className="flex w-[120px] items-center">
              <span className="text-[12px] text-[var(--text-primary)]">
                {order.brand}
              </span>
            </div>

            {/* 狀態 */}
            <div className="flex w-[80px] items-center">
              <span
                className="rounded-full px-2 py-1 text-[11px] font-medium"
                style={{
                  color: order.status.color,
                  backgroundColor: order.status.bg,
                  border: order.status.border
                    ? `1px solid ${order.status.border}`
                    : undefined,
                }}
              >
                {order.status.label}
              </span>
            </div>

            {/* 指派技師 */}
            <div className="flex w-[90px] items-center gap-1">
              {order.technician ? (
                <>
                  <div
                    className="h-[22px] w-[22px] flex-shrink-0 rounded-full"
                    style={{ backgroundColor: order.technician.color }}
                  />
                  <span className="text-[12px] text-[var(--text-primary)]">
                    {order.technician.name}
                  </span>
                </>
              ) : (
                <>
                  <div className="h-[18px] w-[18px] flex-shrink-0 rounded-full border border-[#94A3B8]" />
                  <span className="text-[12px] text-[var(--text-disabled)]">
                    未指派
                  </span>
                </>
              )}
            </div>

            {/* SLA倒數 */}
            <div className="flex w-[100px] items-center">
              <span
                className={`text-[12px] ${order.sla.bold ? "font-bold" : ""}`}
                style={{
                  color: order.sla.color || "var(--text-secondary)",
                }}
              >
                {order.sla.text}
              </span>
            </div>

            {/* 建立時間 */}
            <div className="flex w-[110px] items-center">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {order.time}
              </span>
            </div>

            {/* 操作 */}
            <div className="flex w-[50px] items-center justify-center">
              <span className="text-[18px] font-bold text-[var(--text-secondary)]">
                ···
              </span>
            </div>
          </div>

          <div className="h-px w-full bg-[#F1F5F9]" />
        </div>
      ))}

      {/* Pagination */}
      <div className="flex h-12 items-center justify-between border-t border-[#F1F5F9] px-4">
        <span className="text-[12px] text-[var(--text-secondary)]">
          共 847 筆，第 1-8 筆
        </span>
        <div className="flex items-center gap-1">
          <button className="flex h-7 w-7 items-center justify-center rounded border border-[var(--border)] text-[12px] text-[var(--text-secondary)]">
            &lt;
          </button>
          {["1", "2", "3"].map((page) => (
            <button
              key={page}
              className={`flex h-7 w-7 items-center justify-center rounded text-[12px] ${
                page === "1"
                  ? "bg-[var(--primary)] font-semibold text-white"
                  : "text-[var(--text-secondary)]"
              }`}
            >
              {page}
            </button>
          ))}
          <span className="text-[12px] text-[var(--text-disabled)]">...</span>
          <button className="flex h-7 w-7 items-center justify-center rounded text-[11px] text-[var(--text-secondary)]">
            106
          </button>
          <button className="flex h-7 w-7 items-center justify-center rounded border border-[var(--border)] text-[12px] text-[var(--text-secondary)]">
            &gt;
          </button>
        </div>
      </div>
    </div>
  );
}
