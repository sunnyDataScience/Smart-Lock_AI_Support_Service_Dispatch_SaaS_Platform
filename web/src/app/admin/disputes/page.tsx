"use client";

import { useState } from "react";
import { Image as ImageIcon, ChevronDown } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

interface TypeBadge {
  label: string;
  textColor: string;
  bgColor: string;
}

const typeBadges: TypeBadge[] = [
  { label: "價格", textColor: "#2563EB", bgColor: "#DBEAFE" },
  { label: "品質", textColor: "#7C3AED", bgColor: "#EDE9FE" },
  { label: "保固", textColor: "#059669", bgColor: "#D1FAE5" },
  { label: "取消費", textColor: "#EA580C", bgColor: "#FFEDD5" },
  { label: "結算", textColor: "#DB2777", bgColor: "#FCE7F3" },
];

const statusTabs = ["全部", "待處理", "調解中", "已結案"];

interface DisputeRow {
  id: string;
  type: TypeBadge;
  parties: string;
  amount: string;
  date: string;
  status: { label: string; textColor: string; bgColor: string };
  isSelected: boolean;
}

const rows: DisputeRow[] = [
  {
    id: "DSP-2024-001",
    type: typeBadges[0],
    parties: "王小明 vs 李技師",
    amount: "NT$ 3,500",
    date: "2024-03-15",
    status: { label: "待處理", textColor: "#D97706", bgColor: "#FEF3C7" },
    isSelected: true,
  },
  {
    id: "DSP-2024-002",
    type: typeBadges[1],
    parties: "陳美麗 vs 張師傅",
    amount: "NT$ 8,200",
    date: "2024-03-14",
    status: { label: "調解中", textColor: "#2563EB", bgColor: "#DBEAFE" },
    isSelected: false,
  },
  {
    id: "DSP-2024-003",
    type: typeBadges[2],
    parties: "林大偉 vs 吳師傅",
    amount: "NT$ 12,000",
    date: "2024-03-10",
    status: { label: "已結案", textColor: "#059669", bgColor: "#D1FAE5" },
    isSelected: false,
  },
  {
    id: "DSP-2024-004",
    type: typeBadges[3],
    parties: "黃志強 vs 周技師",
    amount: "NT$ 2,800",
    date: "2024-03-08",
    status: { label: "已駁回", textColor: "#64748B", bgColor: "#F1F5F9" },
    isSelected: false,
  },
];

const columns = [
  { label: "爭議編號", width: "w-[120px]" },
  { label: "類型", width: "w-[80px]" },
  { label: "當事人", width: "flex-1" },
  { label: "爭議金額", width: "w-[100px]" },
  { label: "建立日期", width: "w-[100px]" },
  { label: "狀態", width: "w-[100px]" },
];

function ImagePlaceholder() {
  return (
    <div className="flex h-[90px] w-[120px] items-center justify-center rounded-md bg-[#E2E8F0]">
      <ImageIcon className="h-6 w-6 text-[var(--text-disabled)]" />
    </div>
  );
}

export default function DisputesPage() {
  const [activeTab, setActiveTab] = useState("全部");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
            爭議案件處理
          </h1>

          {/* Filter Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                類型
              </span>
              <div className="flex items-center gap-2">
                {typeBadges.map((badge) => (
                  <span
                    key={badge.label}
                    className="rounded-xl px-3 py-1 text-xs font-medium"
                    style={{
                      color: badge.textColor,
                      backgroundColor: badge.bgColor,
                    }}
                  >
                    {badge.label}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex overflow-hidden rounded-md border border-[var(--border)]">
              {statusTabs.map((tab, idx) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-[14px] py-[6px] text-[13px] font-medium ${
                    activeTab === tab
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--bg-surface)] text-[var(--text-secondary)]"
                  } ${idx > 0 ? "border-l border-[var(--border)]" : ""}`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {/* Dispute Table */}
          <div className="overflow-hidden rounded-lg border border-[var(--border)]">
            <div className="flex h-[44px] items-center border-b border-[var(--border)] bg-[#F8FAFC]">
              {columns.map((col) => (
                <div
                  key={col.label}
                  className={`flex items-center px-3 ${col.width}`}
                >
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {rows.map((row, idx) => (
              <div
                key={row.id}
                className={`flex h-[48px] items-center ${
                  row.isSelected ? "bg-[#EFF6FF]" : "bg-[var(--bg-surface)]"
                } ${
                  idx < rows.length - 1
                    ? "border-b border-[var(--border)]"
                    : ""
                }`}
              >
                <div className="flex w-[120px] items-center px-3">
                  <span className="font-mono text-[13px] font-medium text-[var(--text-primary)]">
                    {row.id}
                  </span>
                </div>

                <div className="flex w-[80px] items-center px-3">
                  <span
                    className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                    style={{
                      color: row.type.textColor,
                      backgroundColor: row.type.bgColor,
                    }}
                  >
                    {row.type.label}
                  </span>
                </div>

                <div className="flex flex-1 items-center px-3">
                  <span className="text-[13px] text-[var(--text-primary)]">
                    {row.parties}
                  </span>
                </div>

                <div className="flex w-[100px] items-center px-3">
                  <span className="text-[13px] font-medium text-[var(--text-primary)]">
                    {row.amount}
                  </span>
                </div>

                <div className="flex w-[100px] items-center px-3">
                  <span className="text-[13px] text-[var(--text-secondary)]">
                    {row.date}
                  </span>
                </div>

                <div className="flex w-[100px] items-center px-3">
                  <span
                    className="rounded-[10px] px-2 py-[2px] text-[11px] font-medium"
                    style={{
                      color: row.status.textColor,
                      backgroundColor: row.status.bgColor,
                    }}
                  >
                    {row.status.label}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Evidence Panel */}
          <div className="flex overflow-hidden rounded-lg border-l-4 border-l-[#BFDBFE] bg-[var(--bg-surface)]">
            {/* Customer Evidence */}
            <div className="flex flex-1 flex-col gap-3 p-5">
              <span className="text-[15px] font-semibold text-[#2563EB]">
                客戶方證據
              </span>
              <div className="flex gap-[10px]">
                <ImagePlaceholder />
                <ImagePlaceholder />
              </div>
              <p className="text-[13px] leading-[1.5] text-[var(--text-primary)]">
                鎖具安裝後無法正常開啟，多次嘗試後仍無法使用。已拍攝鎖具外觀及操作過程影片作為證據。
              </p>
              <span className="text-xs text-[var(--text-secondary)]">
                提交時間：2024-03-15 14:30
              </span>
            </div>

            {/* Divider */}
            <div className="w-px bg-[var(--border)]" />

            {/* Technician Evidence */}
            <div className="flex flex-1 flex-col gap-3 p-5">
              <span className="text-[15px] font-semibold text-[#D97706]">
                技師方證據
              </span>
              <div className="flex gap-[10px]">
                <ImagePlaceholder />
                <ImagePlaceholder />
              </div>
              <p className="text-[13px] leading-[1.5] text-[var(--text-primary)]">
                安裝過程符合標準作業流程，鎖具測試正常。客戶使用方式不當導致故障，已附安裝完成確認單。
              </p>
              <span className="text-xs text-[var(--text-secondary)]">
                提交時間：2024-03-16 09:15
              </span>
            </div>
          </div>

          {/* Resolution Form */}
          <div className="flex flex-col gap-4 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-5">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              調解處理
            </span>

            {/* Textarea */}
            <div className="flex flex-col gap-[6px]">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                調解備註
              </span>
              <textarea
                placeholder="請輸入調解備註內容..."
                className="h-[100px] resize-none rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-3 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>

            {/* Input Row */}
            <div className="flex gap-4">
              <div className="flex flex-1 flex-col gap-[6px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  調解金額 NT$
                </span>
                <input
                  type="text"
                  defaultValue="3,500"
                  className="h-10 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 text-[13px] text-[var(--text-primary)] outline-none"
                />
              </div>
              <div className="flex flex-1 flex-col gap-[6px]">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  調解方式
                </span>
                <button className="flex h-10 items-center justify-between rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3">
                  <span className="text-[13px] text-[var(--text-primary)]">
                    部分退款
                  </span>
                  <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
                </button>
              </div>
            </div>

            {/* Button Row */}
            <div className="flex items-center justify-end gap-3">
              <button className="rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-5 py-[10px] text-sm font-medium text-[var(--text-secondary)]">
                儲存草稿
              </button>
              <button className="rounded-md bg-[var(--primary)] px-5 py-[10px] text-sm font-medium text-white">
                確認調解結果
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
