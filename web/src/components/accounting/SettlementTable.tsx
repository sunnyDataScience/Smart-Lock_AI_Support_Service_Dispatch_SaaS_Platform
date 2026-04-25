"use client";

import { useState } from "react";
import Link from "next/link";
import { Eye, Pencil } from "lucide-react";
import SettlementDetailModal from "@/components/accounting/SettlementDetailModal";

interface Settlement {
  name: string;
  period: string;
  total: string;
  labor: string;
  bonus: string;
  penalty: string;
  status: "draft" | "confirmed" | "paid";
}

const settlements: Settlement[] = [
  { name: "王建明", period: "04/01 - 04/30", total: "$135,200", labor: "$98,000", bonus: "+$12,200", penalty: "-$2,000", status: "draft" },
  { name: "李美玲", period: "04/01 - 04/30", total: "$128,600", labor: "$92,000", bonus: "+$8,600", penalty: "-$1,000", status: "draft" },
  { name: "張志偉", period: "04/01 - 04/30", total: "$142,800", labor: "$105,000", bonus: "+$15,800", penalty: "-$3,000", status: "draft" },
  { name: "陳雅琳", period: "04/01 - 04/30", total: "$118,400", labor: "$88,000", bonus: "+$6,400", penalty: "-$1,500", status: "confirmed" },
  { name: "林俊傑", period: "04/01 - 04/30", total: "$95,600", labor: "$72,000", bonus: "+$5,600", penalty: "-$800", status: "confirmed" },
  { name: "黃淑芬", period: "04/01 - 04/30", total: "$108,200", labor: "$82,000", bonus: "+$9,200", penalty: "-$2,500", status: "confirmed" },
  { name: "吳明哲", period: "04/01 - 04/30", total: "$88,400", labor: "$68,000", bonus: "+$4,400", penalty: "-$1,200", status: "paid" },
  { name: "趙雅婷", period: "04/01 - 04/30", total: "$75,200", labor: "$58,000", bonus: "+$3,200", penalty: "-$800", status: "paid" },
];

const statusConfig = {
  draft: { label: "草稿", textColor: "#64748B", bgColor: "#F1F5F9" },
  confirmed: { label: "已確認", textColor: "#2563EB", bgColor: "#DBEAFE" },
  paid: { label: "已付款", textColor: "#10B981", bgColor: "#D1FAE5" },
};

const columns = [
  { label: "", width: "w-[40px]", justify: "justify-center" },
  { label: "技師", width: "w-[150px]" },
  { label: "期間", width: "w-[160px]" },
  { label: "總額", width: "w-[110px]" },
  { label: "工資", width: "w-[90px]" },
  { label: "獎金", width: "w-[90px]" },
  { label: "扣款", width: "w-[90px]" },
  { label: "狀態", width: "w-[90px]" },
  { label: "操作", width: "flex-1" },
];

export default function SettlementTable() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="flex flex-1 flex-col bg-[var(--bg-surface)]">
      <SettlementDetailModal open={modalOpen} onClose={() => setModalOpen(false)} />
      {/* Batch Action Bar */}
      <div className="flex items-center gap-3 border-b border-[var(--border)] px-8 py-3">
        <div className="h-4 w-4 rounded border-[1.5px] border-[var(--border)]" />
        <span className="text-[13px] text-[var(--text-secondary)]">全選</span>
        <button className="rounded-md bg-[var(--primary)] px-4 py-[7px] text-[13px] font-semibold text-white">
          批次確認
        </button>
        <button className="rounded-md border border-[var(--border)] px-4 py-[7px] text-[13px] font-medium text-[var(--text-primary)]">
          批次標記已付
        </button>
      </div>

      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        <div className="flex w-[40px] items-center justify-center">
          <div className="h-4 w-4 rounded border-[1.5px] border-[var(--border)]" />
        </div>
        {columns.slice(1).map((col) => (
          <div
            key={col.label}
            className={`flex items-center px-2 ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Data Rows */}
      {settlements.map((s) => {
        const badge = statusConfig[s.status];
        return (
          <div
            key={s.name}
            className="flex h-[48px] items-center border-b border-[var(--border)] px-8"
          >
            {/* Checkbox */}
            <div className="flex w-[40px] items-center justify-center">
              <div className="h-4 w-4 rounded border-[1.5px] border-[var(--border)]" />
            </div>

            {/* Name */}
            <div className="flex w-[150px] items-center px-2">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {s.name}
              </span>
            </div>

            {/* Period */}
            <div className="flex w-[160px] items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {s.period}
              </span>
            </div>

            {/* Total */}
            <div className="flex w-[110px] items-center px-2">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {s.total}
              </span>
            </div>

            {/* Labor */}
            <div className="flex w-[90px] items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {s.labor}
              </span>
            </div>

            {/* Bonus */}
            <div className="flex w-[90px] items-center px-2">
              <span className="text-[13px] font-medium text-[#10B981]">
                {s.bonus}
              </span>
            </div>

            {/* Penalty */}
            <div className="flex w-[90px] items-center px-2">
              <span className="text-[13px] font-medium text-[#EF4444]">
                {s.penalty}
              </span>
            </div>

            {/* Status */}
            <div className="flex w-[90px] items-center px-2">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: badge.textColor, backgroundColor: badge.bgColor }}
              >
                {badge.label}
              </span>
            </div>

            {/* Actions */}
            <div className="flex flex-1 items-center gap-1 px-2">
              <button onClick={() => setModalOpen(true)}>
                <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
              </button>
              <Pencil className="h-4 w-4 text-[var(--text-secondary)]" />
            </div>
          </div>
        );
      })}

      {/* Footer Summary */}
      <div className="flex h-[52px] items-center bg-[var(--bg-page)] px-8">
        <div className="w-[40px]" />
        <div className="flex w-[150px] items-center px-2">
          <span className="text-[13px] font-bold text-[var(--text-primary)]">
            合計 (8人)
          </span>
        </div>
        <div className="w-[160px] px-2" />
        <div className="flex w-[110px] items-center px-2">
          <span className="text-[13px] font-bold text-[var(--text-primary)]">
            $892,400
          </span>
        </div>
        <div className="flex w-[90px] items-center px-2">
          <span className="text-[13px] font-semibold text-[var(--text-secondary)]">
            $663,000
          </span>
        </div>
        <div className="flex w-[90px] items-center px-2">
          <span className="text-[13px] font-semibold text-[#10B981]">
            +$65,400
          </span>
        </div>
        <div className="flex w-[90px] items-center px-2">
          <span className="text-[13px] font-semibold text-[#EF4444]">
            -$12,800
          </span>
        </div>
        <div className="w-[90px] px-2" />
        <div className="flex-1" />
      </div>
    </div>
  );
}
