"use client";

import Link from "next/link";
import { X, Trophy, TriangleAlert, Printer, CircleCheck } from "lucide-react";

interface OrderRow {
  id: string;
  serviceType: string;
  serviceColor: string;
  serviceBg: string;
  rate: string;
  orderAmount: string;
  commission: string;
}

interface BonusItem {
  description: string;
  amount: string;
}

interface PenaltyItem {
  description: string;
  amount: string;
}

interface SettlementDetailProps {
  open: boolean;
  onClose: () => void;
}

const orders: OrderRow[] = [
  { id: "WO-2026-0412", serviceType: "一般維修", serviceColor: "#2563EB", serviceBg: "#DBEAFE", rate: "70%", orderAmount: "NT$ 4,500", commission: "NT$ 3,150" },
  { id: "WO-2026-0415", serviceType: "安裝", serviceColor: "#92400E", serviceBg: "#FEF3C7", rate: "60%", orderAmount: "NT$ 8,000", commission: "NT$ 4,800" },
  { id: "WO-2026-0418", serviceType: "一般維修", serviceColor: "#2563EB", serviceBg: "#DBEAFE", rate: "70%", orderAmount: "NT$ 3,200", commission: "NT$ 2,240" },
  { id: "WO-2026-0421", serviceType: "客供材料", serviceColor: "#065F46", serviceBg: "#D1FAE5", rate: "80%", orderAmount: "NT$ 2,800", commission: "NT$ 2,240" },
  { id: "WO-2026-0423", serviceType: "安裝", serviceColor: "#92400E", serviceBg: "#FEF3C7", rate: "60%", orderAmount: "NT$ 12,000", commission: "NT$ 7,200" },
  { id: "WO-2026-0428", serviceType: "一般維修", serviceColor: "#2563EB", serviceBg: "#DBEAFE", rate: "70%", orderAmount: "NT$ 5,600", commission: "NT$ 3,920" },
];

const bonuses: BonusItem[] = [
  { description: "高評價獎金（評分 ≥ 4.8）— WO-2026-0412", amount: "+NT$ 100" },
  { description: "快速完工獎金（比預估快 25%）— WO-2026-0418", amount: "+NT$ 50" },
  { description: "高評價獎金（評分 ≥ 4.8）— WO-2026-0423", amount: "+NT$ 100" },
  { description: "高評價獎金（評分 ≥ 4.8）— WO-2026-0428", amount: "+NT$ 100" },
];

const penalties: PenaltyItem[] = [
  { description: "重工扣款（同一問題二次維修）— WO-2026-0415", amount: "-NT$ 500" },
  { description: "客訴扣款（收到客戶投訴）— WO-2026-0421", amount: "-NT$ 300" },
];

const columns = [
  { label: "工單編號", width: "w-[110px]" },
  { label: "服務類型", width: "w-[100px]" },
  { label: "佣金比例", width: "w-[80px]" },
  { label: "工單金額", width: "w-[110px]" },
  { label: "佣金金額", width: "flex-1" },
];

export default function SettlementDetailModal({ open, onClose }: SettlementDetailProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-[720px] flex-col overflow-hidden rounded-xl bg-[var(--bg-surface)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-5">
          <div className="flex flex-col gap-1">
            <span className="text-lg font-bold text-[var(--text-primary)]">
              陳建宏 結算明細 — 2026/04
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              結算期間：2026/04/01 - 2026/04/30
            </span>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md"
          >
            <X className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-6 py-5">
          {/* Summary Cards */}
          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[var(--bg-page)] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">工資合計</span>
              <span className="text-lg font-bold text-[var(--text-primary)]">NT$ 42,000</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#F0FDF4] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">獎金合計</span>
              <span className="text-lg font-bold text-[#10B981]">NT$ 3,400</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#FEF2F2] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">扣款合計</span>
              <span className="text-lg font-bold text-[#EF4444]">NT$ -800</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#DBEAFE] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">淨結算額</span>
              <span className="text-xl font-bold text-[var(--primary)]">NT$ 44,600</span>
            </div>
          </div>

          {/* Order Commission Table */}
          <div className="flex flex-col gap-[10px]">
            <span className="text-[15px] font-semibold text-[var(--text-primary)]">
              工單佣金明細
            </span>
            <div className="overflow-hidden rounded-lg border border-[var(--border)]">
              {/* Table Header */}
              <div className="flex h-[38px] items-center bg-[var(--bg-page)] px-[14px]">
                {columns.map((col) => (
                  <div key={col.label} className={`${col.width}`}>
                    <span className="text-[11px] font-semibold text-[var(--text-secondary)]">
                      {col.label}
                    </span>
                  </div>
                ))}
              </div>

              {/* Table Rows */}
              {orders.map((order) => (
                <div
                  key={order.id}
                  className="flex h-[40px] items-center border-b border-[var(--border)] px-[14px] last:border-b-0"
                >
                  <div className="w-[110px]">
                    <Link
                      href={`/work-orders/${order.id}`}
                      className="text-xs text-[var(--primary)] hover:underline"
                    >
                      {order.id}
                    </Link>
                  </div>
                  <div className="w-[100px]">
                    <span
                      className="rounded px-2 py-[2px] text-[11px] font-medium"
                      style={{ color: order.serviceColor, backgroundColor: order.serviceBg }}
                    >
                      {order.serviceType}
                    </span>
                  </div>
                  <div className="w-[80px]">
                    <span className="text-xs text-[var(--text-primary)]">{order.rate}</span>
                  </div>
                  <div className="w-[110px]">
                    <span className="text-xs text-[var(--text-primary)]">{order.orderAmount}</span>
                  </div>
                  <div className="flex-1">
                    <span className="text-xs font-semibold text-[var(--text-primary)]">{order.commission}</span>
                  </div>
                </div>
              ))}

              {/* Table Total */}
              <div className="flex h-[40px] items-center bg-[var(--bg-page)] px-[14px]">
                <div className="w-[110px]">
                  <span className="text-xs font-semibold text-[var(--text-primary)]">合計 (6 筆)</span>
                </div>
                <div className="w-[100px]" />
                <div className="w-[80px]" />
                <div className="w-[110px]">
                  <span className="text-xs font-semibold text-[var(--text-primary)]">NT$ 36,100</span>
                </div>
                <div className="flex-1">
                  <span className="text-xs font-bold text-[var(--primary)]">NT$ 23,550</span>
                </div>
              </div>
            </div>
          </div>

          {/* Bonus Section */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-[#10B981]" />
              <span className="text-sm font-semibold text-[var(--text-primary)]">獎金明細</span>
            </div>
            <div className="flex flex-col gap-[6px] rounded-lg bg-[#F0FDF4] px-[14px] py-[10px]">
              {bonuses.map((b, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-[6px]">
                    <div className="h-[6px] w-[6px] rounded-[3px] bg-[#10B981]" />
                    <span className="text-xs text-[var(--text-primary)]">{b.description}</span>
                  </div>
                  <span className="text-[13px] font-semibold text-[#10B981]">{b.amount}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Penalty Section */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <TriangleAlert className="h-4 w-4 text-[#EF4444]" />
              <span className="text-sm font-semibold text-[var(--text-primary)]">扣款明細</span>
            </div>
            <div className="flex flex-col gap-[6px] rounded-lg bg-[#FEF2F2] px-[14px] py-[10px]">
              {penalties.map((p, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-[6px]">
                    <div className="h-[6px] w-[6px] rounded-[3px] bg-[#EF4444]" />
                    <span className="text-xs text-[var(--text-primary)]">{p.description}</span>
                  </div>
                  <span className="text-[13px] font-semibold text-[#EF4444]">{p.amount}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-[var(--border)]" />

          {/* Final Settlement Amount */}
          <div className="flex items-center justify-between rounded-[10px] bg-[#DBEAFE] px-5 py-4">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              最終結算金額
            </span>
            <span className="text-[22px] font-bold text-[var(--primary)]">
              NT$ 44,600
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[var(--border)] px-6 py-4">
          <button className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] px-4 py-2">
            <Printer className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
            <span className="text-[13px] text-[var(--text-primary)]">列印</span>
          </button>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-5 py-[10px]">
              <CircleCheck className="h-4 w-4 text-white" />
              <span className="text-sm font-semibold text-white">確認結算</span>
            </button>
            <button
              onClick={onClose}
              className="rounded-lg border border-[var(--border)] px-5 py-[10px]"
            >
              <span className="text-sm text-[var(--text-secondary)]">關閉</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
