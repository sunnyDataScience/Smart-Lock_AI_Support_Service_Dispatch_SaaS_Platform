"use client";

import { ArrowUpDown } from "lucide-react";

interface PanelItem {
  id: string;
  badge: { label: string; bg: string };
  customer: string;
  address: string;
  brand: string;
  rightText?: string;
  rightColor?: string;
  rightBold?: boolean;
  showAssignBtn?: boolean;
  active?: boolean;
}

const items: PanelItem[] = [
  {
    id: "WO-20260422-0001",
    badge: { label: "已建立", bg: "#6366F1" },
    customer: "陳小姐",
    address: "台北市大安區忠孝東路四段100號12F",
    brand: "Yale YDM-4109",
    rightText: "剩餘 02:45",
    showAssignBtn: true,
    active: true,
  },
  {
    id: "WO-20260422-0002",
    badge: { label: "已派工", bg: "#8B5CF6" },
    customer: "王大明",
    address: "新北市板橋區文化路一段65號3F",
    brand: "Samsung SHP-DP609",
    rightText: "李技師 · 剩餘 01:30",
  },
  {
    id: "WO-20260422-0003",
    badge: { label: "進行中", bg: "#3B82F6" },
    customer: "林美華",
    address: "台中市西屯區台灣大道三段251號8F",
    brand: "Gateman F300",
    rightText: "張師傅 · 剩餘 04:20",
  },
  {
    id: "WO-20260421-0015",
    badge: { label: "延遲中", bg: "#F59E0B" },
    customer: "黃志明",
    address: "高雄市左營區博愛二路366號5F",
    brand: "美樂 ENTR",
    rightText: "謬師傅 · 剩餘 00:25",
    rightColor: "#F59E0B",
    rightBold: true,
  },
  {
    id: "WO-20260421-0012",
    badge: { label: "逾時", bg: "#EF4444" },
    customer: "劉家豪",
    address: "台北市信義區信義路五段7號35F",
    brand: "Philips 9300",
    rightText: "吴技師 · 逾時 01:15",
    rightColor: "#EF4444",
    rightBold: true,
  },
];

interface MapWorkOrderPanelProps {
  onAssign?: (workOrderId: string) => void;
}

export default function MapWorkOrderPanel({ onAssign }: MapWorkOrderPanelProps) {
  return (
    <div className="flex w-[400px] flex-shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-surface)]">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-[14px]">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-[var(--text-primary)]">
            工單列表
          </span>
          <span className="flex h-[22px] items-center justify-center rounded-full bg-[var(--primary)] px-2 text-[11px] font-semibold text-white">
            23
          </span>
        </div>
        <button className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1">
          <ArrowUpDown className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
          <span className="text-[12px] text-[var(--text-secondary)]">
            SLA排序
          </span>
        </button>
      </div>

      {/* Scroll Area */}
      <div className="flex flex-1 flex-col overflow-auto">
        {items.map((item) => (
          <div
            key={item.id}
            className={`flex flex-col gap-2 px-4 py-3 ${
              item.active
                ? "border-b border-[var(--primary)] border-l-[3px] bg-[#EFF6FF]"
                : "border-b border-[var(--border)]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[12px] font-medium text-[var(--primary)]">
                {item.id}
              </span>
              <span
                className="rounded-full px-2 text-[11px] font-medium leading-5 text-white"
                style={{ backgroundColor: item.badge.bg }}
              >
                {item.badge.label}
              </span>
            </div>
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              {item.customer}
            </span>
            <span className="text-[12px] text-[var(--text-secondary)]">
              {item.address}
            </span>
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-[var(--text-secondary)]">
                {item.brand}
              </span>
              <div className="flex items-center gap-2">
                {item.rightText && (
                  <span
                    className={`text-[12px] ${item.rightBold ? "font-bold" : ""}`}
                    style={{ color: item.rightColor || "var(--text-secondary)" }}
                  >
                    {item.rightText}
                  </span>
                )}
                {item.showAssignBtn && (
                  <button
                    className="flex h-[26px] items-center justify-center rounded-md bg-[#F59E0B] px-[10px]"
                    onClick={() => onAssign?.(item.id)}
                  >
                    <span className="text-[11px] font-semibold text-white">
                      指派
                    </span>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        <div className="flex h-10 items-center justify-center">
          <span className="text-[13px] font-medium text-[var(--primary)]">
            載入更多工單...
          </span>
        </div>
      </div>
    </div>
  );
}
