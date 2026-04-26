"use client";

import { useState } from "react";
import {
  Search,
  UserPlus,
  Users,
  ShieldAlert,
  ShieldCheck,
  Clock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Star,
  Eye,
  MoreHorizontal,
  X,
  Lock,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

type RiskLevel = "low" | "medium" | "high" | "blacklisted";
type WarrantyStatus = "active" | "expiring" | "expired" | "none";

interface Customer {
  id: string;
  name: string;
  avatar: string;
  phone: string;
  lineId: string;
  address: string;
  deviceCount: number;
  totalOrders: number;
  satisfactionAvg: number;
  riskLevel: RiskLevel;
  preferredTechnician: string | null;
  warrantyStatus: WarrantyStatus;
  warrantyDaysRemaining: number | null;
  lastServiceAt: string;
}

const customers: Customer[] = [
  {
    id: "C001",
    name: "王建國",
    avatar: "王",
    phone: "0912-345-678",
    lineId: "U1a2b****ef01",
    address: "台北市大安區忠孝東路四段 100 號 3F",
    deviceCount: 3,
    totalOrders: 12,
    satisfactionAvg: 4.7,
    riskLevel: "low",
    preferredTechnician: "陳大明",
    warrantyStatus: "active",
    warrantyDaysRemaining: 185,
    lastServiceAt: "2026-04-18",
  },
  {
    id: "C002",
    name: "林淑芬",
    avatar: "林",
    phone: "0923-456-789",
    lineId: "U2b3c****gh23",
    address: "新北市板橋區文化路一段 200 號",
    deviceCount: 2,
    totalOrders: 8,
    satisfactionAvg: 4.2,
    riskLevel: "low",
    preferredTechnician: "林美玲",
    warrantyStatus: "expiring",
    warrantyDaysRemaining: 22,
    lastServiceAt: "2026-04-10",
  },
  {
    id: "C003",
    name: "張偉明",
    avatar: "張",
    phone: "0934-567-890",
    lineId: "U3c4d****ij45",
    address: "台中市西屯區台灣大道三段 99 號 12F",
    deviceCount: 5,
    totalOrders: 23,
    satisfactionAvg: 3.8,
    riskLevel: "medium",
    preferredTechnician: null,
    warrantyStatus: "active",
    warrantyDaysRemaining: 340,
    lastServiceAt: "2026-04-20",
  },
  {
    id: "C004",
    name: "陳美玲",
    avatar: "陳",
    phone: "0945-678-901",
    lineId: "U4d5e****kl67",
    address: "高雄市前鎮區中山二路 300 號",
    deviceCount: 1,
    totalOrders: 4,
    satisfactionAvg: 2.3,
    riskLevel: "high",
    preferredTechnician: "張志豪",
    warrantyStatus: "expired",
    warrantyDaysRemaining: null,
    lastServiceAt: "2026-03-15",
  },
  {
    id: "C005",
    name: "黃志豪",
    avatar: "黃",
    phone: "0956-789-012",
    lineId: "U5e6f****mn89",
    address: "台北市信義區松仁路 50 號 8F-1",
    deviceCount: 4,
    totalOrders: 15,
    satisfactionAvg: 4.5,
    riskLevel: "low",
    preferredTechnician: "陳大明",
    warrantyStatus: "active",
    warrantyDaysRemaining: 120,
    lastServiceAt: "2026-04-22",
  },
  {
    id: "C006",
    name: "李雅婷",
    avatar: "李",
    phone: "0967-890-123",
    lineId: "U6f7g****op01",
    address: "新竹市東區光復路二段 101 號",
    deviceCount: 2,
    totalOrders: 6,
    satisfactionAvg: 2.8,
    riskLevel: "high",
    preferredTechnician: null,
    warrantyStatus: "expiring",
    warrantyDaysRemaining: 15,
    lastServiceAt: "2026-04-05",
  },
  {
    id: "C007",
    name: "吳宗翰",
    avatar: "吳",
    phone: "0978-901-234",
    lineId: "U7g8h****qr23",
    address: "台南市中西區民生路一段 88 號",
    deviceCount: 1,
    totalOrders: 2,
    satisfactionAvg: 5.0,
    riskLevel: "low",
    preferredTechnician: null,
    warrantyStatus: "active",
    warrantyDaysRemaining: 280,
    lastServiceAt: "2026-04-12",
  },
  {
    id: "C008",
    name: "劉國強",
    avatar: "劉",
    phone: "0989-012-345",
    lineId: "—",
    address: "桃園市中壢區中央西路二段 55 號 2F",
    deviceCount: 3,
    totalOrders: 19,
    satisfactionAvg: 1.9,
    riskLevel: "blacklisted",
    preferredTechnician: null,
    warrantyStatus: "expired",
    warrantyDaysRemaining: null,
    lastServiceAt: "2026-02-28",
  },
  {
    id: "C009",
    name: "許芳瑜",
    avatar: "許",
    phone: "0910-123-456",
    lineId: "U9i0j****uv67",
    address: "台北市中山區南京東路三段 168 號 5F",
    deviceCount: 2,
    totalOrders: 7,
    satisfactionAvg: 4.0,
    riskLevel: "medium",
    preferredTechnician: "王建華",
    warrantyStatus: "expiring",
    warrantyDaysRemaining: 28,
    lastServiceAt: "2026-04-16",
  },
  {
    id: "C010",
    name: "蔡明德",
    avatar: "蔡",
    phone: "0921-234-567",
    lineId: "Ua1b2****wx89",
    address: "台中市北屯區文心路四段 200 號",
    deviceCount: 6,
    totalOrders: 31,
    satisfactionAvg: 3.5,
    riskLevel: "medium",
    preferredTechnician: "李佳穎",
    warrantyStatus: "active",
    warrantyDaysRemaining: 95,
    lastServiceAt: "2026-04-21",
  },
];

const summary = {
  total: 1284,
  active: 876,
  activeChange: 3.2,
  highRisk: 47,
  warrantyExpiring: 23,
};

const riskConfig: Record<
  RiskLevel,
  { label: string; bg: string; text: string }
> = {
  low: { label: "低風險", bg: "bg-green-100", text: "text-green-700" },
  medium: { label: "中風險", bg: "bg-amber-100", text: "text-amber-700" },
  high: { label: "高風險", bg: "bg-red-100", text: "text-red-700 font-bold" },
  blacklisted: { label: "黑名單", bg: "bg-gray-900", text: "text-white" },
};

function RiskBadge({ level }: { level: RiskLevel }) {
  const c = riskConfig[level];
  return (
    <span
      className={`rounded-md px-2 py-[3px] text-[11px] font-medium ${c.bg} ${c.text}`}
    >
      {c.label}
    </span>
  );
}

function SatisfactionStars({ value }: { value: number }) {
  const color =
    value < 3.0
      ? "text-red-600"
      : value < 4.0
        ? "text-amber-600"
        : "text-green-600";
  return (
    <div className={`flex items-center gap-1 ${color}`}>
      <Star className="h-3 w-3 fill-current" />
      <span className="text-[13px] font-medium">{value.toFixed(1)}</span>
    </div>
  );
}

function WarrantyIndicator({
  status,
  days,
}: {
  status: WarrantyStatus;
  days: number | null;
}) {
  if (status === "none") return <span className="text-[13px] text-[var(--text-disabled)]">—</span>;
  if (status === "active")
    return <ShieldCheck className="h-4 w-4 text-green-600" />;
  if (status === "expiring")
    return (
      <div className="flex items-center gap-1">
        <Clock className="h-4 w-4 text-amber-500" />
        <span className="text-xs text-amber-600">{days}天</span>
      </div>
    );
  return (
    <div className="flex items-center gap-1">
      <X className="h-4 w-4 text-red-500" />
      <span className="text-xs text-red-600">已過期</span>
    </div>
  );
}

const columns = [
  { label: "客戶", width: "w-[200px]" },
  { label: "LINE ID", width: "w-[130px]" },
  { label: "地址", width: "w-[200px]" },
  { label: "設備", width: "w-[70px]" },
  { label: "工單", width: "w-[60px]" },
  { label: "滿意度", width: "w-[80px]" },
  { label: "風險", width: "w-[80px]" },
  { label: "偏好技師", width: "w-[90px]" },
  { label: "保固", width: "w-[80px]" },
  { label: "", width: "w-[60px]" },
];

export default function CustomersPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  const handleFilterToggle = (filter: string) => {
    setActiveFilters((prev) =>
      prev.includes(filter)
        ? prev.filter((f) => f !== filter)
        : [...prev, filter]
    );
  };

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
                客戶主檔
              </h1>
              <span className="flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-[2px] text-xs text-[var(--primary)]">
                <Lock className="h-3 w-3" />
                SmartLock 租戶
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex w-80 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
                <Search className="h-4 w-4 text-[var(--text-disabled)]" />
                <input
                  type="text"
                  placeholder="搜尋姓名 / 電話 / LINE ID / 地址…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")}>
                    <X className="h-4 w-4 text-[var(--text-disabled)]" />
                  </button>
                )}
              </div>
              <button className="flex items-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2">
                <UserPlus className="h-4 w-4 text-white" />
                <span className="text-[13px] font-medium text-white">
                  新增客戶
                </span>
              </button>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
                <Users className="h-5 w-5 text-[var(--primary)]" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  總客戶數
                </span>
                <span className="text-xl font-bold text-[var(--text-primary)]">
                  {summary.total.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
                <Users className="h-5 w-5 text-green-600" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-[var(--text-secondary)]">
                  活躍客戶
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold text-[var(--text-primary)]">
                    {summary.active.toLocaleString()}
                  </span>
                  <span className="text-xs font-semibold text-green-600">
                    ↑{summary.activeChange}%
                  </span>
                </div>
              </div>
            </div>

            <button className="flex items-center gap-4 rounded-xl bg-red-50 p-4 text-left">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100">
                <ShieldAlert className="h-5 w-5 text-red-600" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-red-600">高風險客戶</span>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold text-red-700">
                    {summary.highRisk}
                  </span>
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
                  </span>
                </div>
              </div>
            </button>

            <button className="flex items-center gap-4 rounded-xl bg-amber-50 p-4 text-left">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
                <Clock className="h-5 w-5 text-amber-600" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-amber-600">30 天內保固到期</span>
                <span className="text-xl font-bold text-amber-700">
                  {summary.warrantyExpiring}
                </span>
              </div>
            </button>
          </div>

          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-4">
            <button
              onClick={() => handleFilterToggle("risk")}
              className={`flex items-center gap-2 rounded-lg border px-3 py-[7px] text-[13px] ${
                activeFilters.includes("risk")
                  ? "border-[var(--primary)] bg-blue-50 text-[var(--primary)]"
                  : "border-[var(--border)] text-[var(--text-primary)]"
              }`}
            >
              風險等級
              <ChevronDown className="h-3 w-3 text-[var(--text-secondary)]" />
            </button>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)]">
              設備品牌
              <ChevronDown className="h-3 w-3 text-[var(--text-secondary)]" />
            </button>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)]">
              保固狀態
              <ChevronDown className="h-3 w-3 text-[var(--text-secondary)]" />
            </button>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-[7px] text-[13px] text-[var(--text-primary)]">
              偏好技師
              <ChevronDown className="h-3 w-3 text-[var(--text-secondary)]" />
            </button>

            {activeFilters.length > 0 && (
              <>
                <span className="rounded-md bg-blue-100 px-2 py-1 text-xs font-medium text-[var(--primary)]">
                  已套用 {activeFilters.length} 個篩選
                </span>
                <button
                  onClick={() => setActiveFilters([])}
                  className="text-[13px] font-medium text-[var(--text-secondary)]"
                >
                  清除全部
                </button>
              </>
            )}
          </div>

          {/* Data Table */}
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            {/* Table Header */}
            <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
              {columns.map((col) => (
                <div
                  key={col.label || "actions"}
                  className={col.width}
                >
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Table Rows */}
            {customers.map((customer) => (
              <div
                key={customer.id}
                className={`group flex cursor-pointer items-center border-t border-[var(--border)] px-4 py-3 transition-colors ${
                  customer.riskLevel === "high" || customer.riskLevel === "blacklisted"
                    ? "hover:bg-red-50"
                    : "hover:bg-blue-50"
                }`}
              >
                {/* Customer Name + Avatar + Phone */}
                <div className="flex w-[200px] items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-xs font-semibold text-[var(--primary)]">
                    {customer.avatar}
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[13px] font-medium text-[var(--text-primary)]">
                      {customer.name}
                    </span>
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      {customer.phone}
                    </span>
                  </div>
                </div>

                {/* LINE ID (masked) */}
                <div className="w-[130px]">
                  <span
                    className="font-['IBM_Plex_Mono'] text-xs text-[var(--text-secondary)]"
                    title={customer.lineId === "—" ? undefined : "hover 顯示完整 ID"}
                  >
                    {customer.lineId}
                  </span>
                </div>

                {/* Address (truncated) */}
                <div className="w-[200px]">
                  <span
                    className="truncate text-[13px] text-[var(--text-primary)]"
                    title={customer.address}
                  >
                    {customer.address.length > 18
                      ? customer.address.slice(0, 18) + "…"
                      : customer.address}
                  </span>
                </div>

                {/* Device Count */}
                <div className="w-[70px]">
                  <span className="rounded-md bg-[#F1F5F9] px-2 py-[2px] text-xs font-medium text-[var(--text-secondary)]">
                    {customer.deviceCount} 台
                  </span>
                </div>

                {/* Total Orders */}
                <div className="w-[60px]">
                  <span className="text-[13px] text-[var(--text-primary)]">
                    {customer.totalOrders}
                  </span>
                </div>

                {/* Satisfaction */}
                <div className="w-[80px]">
                  <SatisfactionStars value={customer.satisfactionAvg} />
                </div>

                {/* Risk Level */}
                <div className="w-[80px]">
                  <RiskBadge level={customer.riskLevel} />
                </div>

                {/* Preferred Technician */}
                <div className="w-[90px]">
                  <span className="text-[13px] italic text-[var(--text-secondary)]">
                    {customer.preferredTechnician ?? "—"}
                  </span>
                </div>

                {/* Warranty */}
                <div className="w-[80px]">
                  <WarrantyIndicator
                    status={customer.warrantyStatus}
                    days={customer.warrantyDaysRemaining}
                  />
                </div>

                {/* Actions */}
                <div className="flex w-[60px] items-center gap-1">
                  <button className="rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
                  </button>
                  <button className="rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <MoreHorizontal className="h-4 w-4 text-[var(--text-secondary)]" />
                  </button>
                </div>
              </div>
            ))}

            {/* Pagination */}
            <div className="flex items-center justify-between border-t border-[var(--border)] px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  顯示 1-10，共 {summary.total.toLocaleString()} 筆
                </span>
                <select className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2 py-1 text-xs text-[var(--text-primary)]">
                  <option>每頁 20</option>
                  <option>每頁 50</option>
                  <option>每頁 100</option>
                </select>
              </div>
              <div className="flex gap-1">
                <button className="rounded-md border border-[var(--border)] p-[6px] text-[var(--text-secondary)]">
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button className="rounded-md bg-[var(--primary)] px-3 py-[6px] text-xs font-semibold text-white">
                  1
                </button>
                <button className="rounded-md border border-[var(--border)] px-3 py-[6px] text-xs text-[var(--text-primary)]">
                  2
                </button>
                <button className="rounded-md border border-[var(--border)] px-3 py-[6px] text-xs text-[var(--text-primary)]">
                  3
                </button>
                <span className="px-1 py-[6px] text-xs text-[var(--text-secondary)]">
                  …
                </span>
                <button className="rounded-md border border-[var(--border)] px-3 py-[6px] text-xs text-[var(--text-primary)]">
                  65
                </button>
                <button className="rounded-md border border-[var(--border)] p-[6px] text-[var(--text-secondary)]">
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
