"use client";

import Sidebar from "@/components/layout/Sidebar";
import RefundReviewTable from "@/components/admin/RefundReviewTable";

interface SlaCard {
  label: string;
  count: number;
  labelColor: string;
  countColor: string;
  bgColor: string;
}

const slaCards: SlaCard[] = [
  {
    label: "SLA ≤ 2小時",
    count: 2,
    labelColor: "#991B1B",
    countColor: "#DC2626",
    bgColor: "#FEE2E2",
  },
  {
    label: "SLA ≤ 8小時",
    count: 5,
    labelColor: "#92400E",
    countColor: "#D97706",
    bgColor: "#FEF3C7",
  },
  {
    label: "SLA > 8小時",
    count: 8,
    labelColor: "#065F46",
    countColor: "#059669",
    bgColor: "#D1FAE5",
  },
];

export default function RefundReviewPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            退款審核佇列
          </h1>

          <div className="flex gap-3">
            {slaCards.map((card) => (
              <div
                key={card.label}
                className="flex flex-1 flex-col gap-1 rounded-lg px-4 py-3"
                style={{ backgroundColor: card.bgColor }}
              >
                <span
                  className="text-[13px] font-medium"
                  style={{ color: card.labelColor }}
                >
                  {card.label}
                </span>
                <span
                  className="text-[28px] font-bold"
                  style={{ color: card.countColor }}
                >
                  {card.count}
                </span>
              </div>
            ))}
          </div>

          <RefundReviewTable />
        </div>
      </div>
    </div>
  );
}
