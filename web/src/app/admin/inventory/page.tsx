"use client";

import { useState } from "react";
import { Plus, Search, ChevronDown } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import InventoryTable from "@/components/admin/InventoryTable";

interface SummaryCard {
  label: string;
  value: number;
  textColor: string;
  bgColor: string;
  borderColor: string;
}

const summaryCards: SummaryCard[] = [
  {
    label: "物料品項",
    value: 156,
    textColor: "var(--text-primary)",
    bgColor: "var(--bg-surface)",
    borderColor: "var(--border)",
  },
  {
    label: "低庫存警示",
    value: 12,
    textColor: "#92400E",
    bgColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  {
    label: "缺貨品項",
    value: 3,
    textColor: "#991B1B",
    bgColor: "#FEF2F2",
    borderColor: "#FECACA",
  },
];

export default function InventoryPage() {
  const [category, setCategory] = useState("");
  const [stockStatus, setStockStatus] = useState("");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              物料庫存管理
            </h1>
            <button className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-4 py-[10px] text-sm font-medium text-white">
              <Plus className="h-4 w-4" />
              新增物料
            </button>
          </div>

          <div className="flex gap-4">
            {summaryCards.map((card) => (
              <div
                key={card.label}
                className="flex flex-1 flex-col gap-1 rounded-lg border px-4 py-3"
                style={{
                  backgroundColor: card.bgColor,
                  borderColor: card.borderColor,
                }}
              >
                <span
                  className="text-[13px] font-medium"
                  style={{ color: card.textColor }}
                >
                  {card.label}
                </span>
                <span
                  className="text-[28px] font-bold"
                  style={{ color: card.textColor }}
                >
                  {card.value}
                </span>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <Search className="h-4 w-4 text-[var(--text-secondary)]" />
              <input
                type="text"
                placeholder="搜尋物料名稱或 SKU..."
                className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>
            <button className="flex w-[160px] items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                物料類別
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
            <button className="flex w-[160px] items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                庫存狀態
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          </div>

          <InventoryTable />
        </div>
      </div>
    </div>
  );
}
