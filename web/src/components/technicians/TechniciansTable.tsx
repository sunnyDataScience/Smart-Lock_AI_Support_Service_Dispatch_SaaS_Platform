"use client";

import { Star, Ellipsis, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

interface Brand {
  name: string;
  textColor: string;
  bgColor: string;
}

interface Technician {
  id: string;
  name: string;
  phone: string;
  avatarColor: string;
  brands: Brand[];
  region: string;
  rating: string;
  status: { label: string; textColor: string; bgColor: string };
  activeOrders: string;
  activeOrderColor: string;
}

const technicians: Technician[] = [
  {
    id: "T001",
    name: "陳建宏",
    phone: "0912-345-678",
    avatarColor: "#DBEAFE",
    brands: [
      { name: "Yale", textColor: "#92400E", bgColor: "#FEF3C7" },
      { name: "Samsung", textColor: "#1E40AF", bgColor: "#DBEAFE" },
    ],
    region: "台北市、新北市",
    rating: "4.8",
    status: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
    activeOrders: "3",
    activeOrderColor: "var(--primary)",
  },
  {
    id: "T002",
    name: "林志明",
    phone: "0923-456-789",
    avatarColor: "#FEF3C7",
    brands: [
      { name: "Gateman", textColor: "#3730A3", bgColor: "#E0E7FF" },
      { name: "Yale", textColor: "#92400E", bgColor: "#FEF3C7" },
    ],
    region: "桃園市、新竹市",
    rating: "4.6",
    status: { label: "外出中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
    activeOrders: "2",
    activeOrderColor: "var(--primary)",
  },
  {
    id: "T003",
    name: "王大偉",
    phone: "0934-567-890",
    avatarColor: "#FCE7F3",
    brands: [
      { name: "Samsung", textColor: "#1E40AF", bgColor: "#DBEAFE" },
      { name: "Milre", textColor: "#065F46", bgColor: "#D1FAE5" },
    ],
    region: "台中市、彰化縣",
    rating: "4.5",
    status: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
    activeOrders: "1",
    activeOrderColor: "var(--primary)",
  },
  {
    id: "T004",
    name: "張家豪",
    phone: "0945-678-901",
    avatarColor: "#E0E7FF",
    brands: [
      { name: "Yale", textColor: "#92400E", bgColor: "#FEF3C7" },
      { name: "Gateman", textColor: "#3730A3", bgColor: "#E0E7FF" },
      { name: "Samsung", textColor: "#1E40AF", bgColor: "#DBEAFE" },
    ],
    region: "台北市、基隆市",
    rating: "4.9",
    status: { label: "休假中", textColor: "#92400E", bgColor: "#FEF3C7" },
    activeOrders: "0",
    activeOrderColor: "var(--text-secondary)",
  },
  {
    id: "T005",
    name: "李國華",
    phone: "0956-789-012",
    avatarColor: "#D1FAE5",
    brands: [
      { name: "Yale", textColor: "#92400E", bgColor: "#FEF3C7" },
    ],
    region: "高雄市、屏東縣",
    rating: "4.3",
    status: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
    activeOrders: "2",
    activeOrderColor: "var(--primary)",
  },
  {
    id: "T006",
    name: "黃文賢",
    phone: "0967-890-123",
    avatarColor: "#FEE2E2",
    brands: [
      { name: "Milre", textColor: "#065F46", bgColor: "#D1FAE5" },
    ],
    region: "台南市、嘉義市",
    rating: "3.9",
    status: { label: "停權", textColor: "#991B1B", bgColor: "#FEE2E2" },
    activeOrders: "0",
    activeOrderColor: "var(--text-secondary)",
  },
  {
    id: "T007",
    name: "吳明德",
    phone: "0978-901-234",
    avatarColor: "#F3E8FF",
    brands: [
      { name: "Samsung", textColor: "#1E40AF", bgColor: "#DBEAFE" },
      { name: "Yale", textColor: "#92400E", bgColor: "#FEF3C7" },
    ],
    region: "新北市、宜蘭縣",
    rating: "4.7",
    status: { label: "外出中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
    activeOrders: "4",
    activeOrderColor: "var(--primary)",
  },
  {
    id: "T008",
    name: "蔡志強",
    phone: "0989-012-345",
    avatarColor: "#FFEDD5",
    brands: [
      { name: "Gateman", textColor: "#3730A3", bgColor: "#E0E7FF" },
    ],
    region: "桃園市、新竹縣",
    rating: "4.4",
    status: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
    activeOrders: "1",
    activeOrderColor: "var(--primary)",
  },
];

const columns = [
  { label: "", width: "w-[52px]" },
  { label: "技師", width: "w-[200px]" },
  { label: "專長品牌", width: "w-[180px]" },
  { label: "服務區域", width: "w-[120px]" },
  { label: "評分", width: "w-[80px]" },
  { label: "狀態", width: "w-[80px]" },
  { label: "進行中工單", width: "w-[100px]" },
  { label: "操作", width: "flex-1" },
];

export default function TechniciansTable() {
  return (
    <div className="flex flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        <div className="flex w-[52px] items-center">
          <div className="h-[18px] w-[18px] rounded border-[1.5px] border-[var(--border)]" />
        </div>
        {columns.slice(1).map((col) => (
          <div key={col.label} className={`flex items-center ${col.width}`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Rows */}
      {technicians.map((t) => (
        <div
          key={t.id}
          className="flex h-[60px] items-center border-b border-[var(--border)] px-8"
        >
          {/* Checkbox */}
          <div className="flex w-[52px] items-center">
            <div className="h-[18px] w-[18px] rounded border-[1.5px] border-[var(--border)]" />
          </div>

          {/* Tech info */}
          <div className="flex w-[200px] items-center gap-[10px]">
            <div
              className="h-9 w-9 flex-shrink-0 rounded-full"
              style={{ backgroundColor: t.avatarColor }}
            />
            <div className="flex flex-col gap-[2px]">
              <Link
                href={`/technicians/${t.id}`}
                className="text-[14px] font-medium text-[var(--text-primary)] hover:underline"
              >
                {t.name}
              </Link>
              <span className="text-[11px] text-[var(--text-secondary)]">
                {t.phone}
              </span>
            </div>
          </div>

          {/* Brands */}
          <div className="flex w-[180px] items-center gap-1">
            {t.brands.map((b) => (
              <span
                key={b.name}
                className="rounded px-2 py-[2px] text-[11px] font-medium"
                style={{ color: b.textColor, backgroundColor: b.bgColor }}
              >
                {b.name}
              </span>
            ))}
          </div>

          {/* Region */}
          <div className="flex w-[120px] items-center">
            <span className="text-[13px] text-[var(--text-primary)]">
              {t.region}
            </span>
          </div>

          {/* Rating */}
          <div className="flex w-[80px] items-center gap-1">
            <Star className="h-[14px] w-[14px] fill-[var(--accent)] text-[var(--accent)]" />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              {t.rating}
            </span>
          </div>

          {/* Status */}
          <div className="flex w-[80px] items-center">
            <span
              className="rounded-full px-[10px] py-[3px] text-[12px] font-medium"
              style={{ color: t.status.textColor, backgroundColor: t.status.bgColor }}
            >
              {t.status.label}
            </span>
          </div>

          {/* Active Orders */}
          <div className="flex w-[100px] items-center">
            <span
              className="text-[14px] font-semibold"
              style={{ color: t.activeOrderColor }}
            >
              {t.activeOrders}
            </span>
          </div>

          {/* Actions */}
          <div className="flex flex-1 items-center">
            <Ellipsis className="h-5 w-5 text-[var(--text-secondary)]" />
          </div>
        </div>
      ))}

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-[var(--border)] px-8 py-3">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 1-8 筆，共 48 筆
        </span>
        <div className="flex items-center gap-1">
          <button className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)]">
            <ChevronLeft className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>
          {["1", "2", "3", "...", "6"].map((p, i) => (
            <button
              key={i}
              className={`flex h-8 w-8 items-center justify-center rounded-md text-[13px] ${
                p === "1"
                  ? "bg-[var(--primary)] font-semibold text-white"
                  : "text-[var(--text-secondary)]"
              }`}
            >
              {p}
            </button>
          ))}
          <button className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)]">
            <ChevronRight className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>
        </div>
      </div>
    </div>
  );
}
