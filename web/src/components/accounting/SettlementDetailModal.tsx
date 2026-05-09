"use client";

import { useMemo } from "react";
import Link from "next/link";
import { X, Trophy, TriangleAlert, Printer, CircleCheck } from "lucide-react";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type ServiceTypeKey = "repair" | "install" | "customMaterial";

interface OrderRow {
  id: string;
  serviceTypeKey: ServiceTypeKey;
  serviceColor: string;
  serviceBg: string;
  rate: string;
  orderAmount: string;
  commission: string;
}

type BonusKey = "highRating" | "fastFinish";
type PenaltyKey = "rework" | "complaint";

interface BonusItem {
  key: BonusKey;
  orderId: string;
  amount: string;
}

interface PenaltyItem {
  key: PenaltyKey;
  orderId: string;
  amount: string;
}

interface SettlementDetailProps {
  open: boolean;
  onClose: () => void;
}

// Service type tone — color/bg fixed per category, label is i18n
const SERVICE_TYPE_TONE: Record<ServiceTypeKey, { color: string; bg: string }> = {
  repair: { color: "#2563EB", bg: "#DBEAFE" },
  install: { color: "#92400E", bg: "#FEF3C7" },
  customMaterial: { color: "#065F46", bg: "#D1FAE5" },
};

const orders: OrderRow[] = [
  { id: "WO-2026-0412", serviceTypeKey: "repair", serviceColor: SERVICE_TYPE_TONE.repair.color, serviceBg: SERVICE_TYPE_TONE.repair.bg, rate: "70%", orderAmount: "NT$ 4,500", commission: "NT$ 3,150" },
  { id: "WO-2026-0415", serviceTypeKey: "install", serviceColor: SERVICE_TYPE_TONE.install.color, serviceBg: SERVICE_TYPE_TONE.install.bg, rate: "60%", orderAmount: "NT$ 8,000", commission: "NT$ 4,800" },
  { id: "WO-2026-0418", serviceTypeKey: "repair", serviceColor: SERVICE_TYPE_TONE.repair.color, serviceBg: SERVICE_TYPE_TONE.repair.bg, rate: "70%", orderAmount: "NT$ 3,200", commission: "NT$ 2,240" },
  { id: "WO-2026-0421", serviceTypeKey: "customMaterial", serviceColor: SERVICE_TYPE_TONE.customMaterial.color, serviceBg: SERVICE_TYPE_TONE.customMaterial.bg, rate: "80%", orderAmount: "NT$ 2,800", commission: "NT$ 2,240" },
  { id: "WO-2026-0423", serviceTypeKey: "install", serviceColor: SERVICE_TYPE_TONE.install.color, serviceBg: SERVICE_TYPE_TONE.install.bg, rate: "60%", orderAmount: "NT$ 12,000", commission: "NT$ 7,200" },
  { id: "WO-2026-0428", serviceTypeKey: "repair", serviceColor: SERVICE_TYPE_TONE.repair.color, serviceBg: SERVICE_TYPE_TONE.repair.bg, rate: "70%", orderAmount: "NT$ 5,600", commission: "NT$ 3,920" },
];

const bonuses: BonusItem[] = [
  { key: "highRating", orderId: "WO-2026-0412", amount: "+NT$ 100" },
  { key: "fastFinish", orderId: "WO-2026-0418", amount: "+NT$ 50" },
  { key: "highRating", orderId: "WO-2026-0423", amount: "+NT$ 100" },
  { key: "highRating", orderId: "WO-2026-0428", amount: "+NT$ 100" },
];

const penalties: PenaltyItem[] = [
  { key: "rework", orderId: "WO-2026-0415", amount: "-NT$ 500" },
  { key: "complaint", orderId: "WO-2026-0421", amount: "-NT$ 300" },
];

export default function SettlementDetailModal({ open, onClose }: SettlementDetailProps) {
  const t = useTranslations("components.accounting.settlementDetailModal");

  const columns = useMemo(
    () => [
      { label: t("cols.orderId"), width: "w-[110px]" },
      { label: t("cols.serviceType"), width: "w-[100px]" },
      { label: t("cols.rate"), width: "w-[80px]" },
      { label: t("cols.orderAmount"), width: "w-[110px]" },
      { label: t("cols.commission"), width: "flex-1" },
    ],
    [t],
  );

  const serviceTypeLabel: Record<ServiceTypeKey, string> = useMemo(
    () => ({
      repair: t("serviceType.repair"),
      install: t("serviceType.install"),
      customMaterial: t("serviceType.customMaterial"),
    }),
    [t],
  );

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
              {t("title", { technician: t("mockTechName"), month: t("mockMonth") })}
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {t("period", { period: t("mockPeriod") })}
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
              <span className="text-xs text-[var(--text-secondary)]">{t("summary.labor")}</span>
              <span className="text-lg font-bold text-[var(--text-primary)]">NT$ 42,000</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#F0FDF4] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">{t("summary.bonus")}</span>
              <span className="text-lg font-bold text-[#10B981]">NT$ 3,400</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#FEF2F2] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">{t("summary.penalty")}</span>
              <span className="text-lg font-bold text-[#EF4444]">NT$ -800</span>
            </div>
            <div className="flex flex-1 flex-col gap-1 rounded-lg bg-[#DBEAFE] p-[14px]">
              <span className="text-xs text-[var(--text-secondary)]">{t("summary.net")}</span>
              <span className="text-xl font-bold text-[var(--primary)]">NT$ 44,600</span>
            </div>
          </div>

          {/* Order Commission Table */}
          <div className="flex flex-col gap-[10px]">
            <span className="text-[15px] font-semibold text-[var(--text-primary)]">
              {t("ordersTitle")}
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
                      {serviceTypeLabel[order.serviceTypeKey]}
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
                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                    {t("totalRow", { count: orders.length })}
                  </span>
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
              <span className="text-sm font-semibold text-[var(--text-primary)]">{t("bonusTitle")}</span>
            </div>
            <div className="flex flex-col gap-[6px] rounded-lg bg-[#F0FDF4] px-[14px] py-[10px]">
              {bonuses.map((b, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-[6px]">
                    <div className="h-[6px] w-[6px] rounded-[3px] bg-[#10B981]" />
                    <span className="text-xs text-[var(--text-primary)]">
                      {t(`bonus.${b.key}`, { orderId: b.orderId })}
                    </span>
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
              <span className="text-sm font-semibold text-[var(--text-primary)]">{t("penaltyTitle")}</span>
            </div>
            <div className="flex flex-col gap-[6px] rounded-lg bg-[#FEF2F2] px-[14px] py-[10px]">
              {penalties.map((p, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-[6px]">
                    <div className="h-[6px] w-[6px] rounded-[3px] bg-[#EF4444]" />
                    <span className="text-xs text-[var(--text-primary)]">
                      {t(`penalty.${p.key}`, { orderId: p.orderId })}
                    </span>
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
              {t("finalAmount")}
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
            <span className="text-[13px] text-[var(--text-primary)]">{t("print")}</span>
          </button>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-5 py-[10px]">
              <CircleCheck className="h-4 w-4 text-white" />
              <span className="text-sm font-semibold text-white">{t("confirm")}</span>
            </button>
            <button
              onClick={onClose}
              className="rounded-lg border border-[var(--border)] px-5 py-[10px]"
            >
              <span className="text-sm text-[var(--text-secondary)]">{t("close")}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
