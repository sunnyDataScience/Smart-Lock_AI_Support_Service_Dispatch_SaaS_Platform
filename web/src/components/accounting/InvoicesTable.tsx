"use client";

import { Eye, RefreshCw, TriangleAlert, ChevronLeft, ChevronRight } from "lucide-react";

interface Invoice {
  id: string;
  workOrder: string;
  customer: string;
  amount: string;
  status: "overdue" | "pending" | "paid" | "disputed";
  paymentMethod: string;
  issueDate: string;
  dueDate: string;
}

const invoices: Invoice[] = [
  { id: "INV-2026-0401", workOrder: "WO-1234", customer: "台北101管委會", amount: "$45,000", status: "overdue", paymentMethod: "月結30天", issueDate: "2026/04/01", dueDate: "2026/04/15" },
  { id: "INV-2026-0402", workOrder: "WO-1235", customer: "遠東百貨", amount: "$28,500", status: "pending", paymentMethod: "貨到付款", issueDate: "2026/04/03", dueDate: "2026/04/20" },
  { id: "INV-2026-0403", workOrder: "WO-1236", customer: "新光三越", amount: "$62,000", status: "paid", paymentMethod: "銀行轉帳", issueDate: "2026/04/05", dueDate: "2026/04/25" },
  { id: "INV-2026-0404", workOrder: "WO-1237", customer: "王小明", amount: "$8,500", status: "paid", paymentMethod: "信用卡", issueDate: "2026/04/06", dueDate: "2026/04/26" },
  { id: "INV-2026-0405", workOrder: "WO-1238", customer: "中華電信", amount: "$156,000", status: "disputed", paymentMethod: "月結30天", issueDate: "2026/04/08", dueDate: "2026/04/28" },
  { id: "INV-2026-0406", workOrder: "WO-1239", customer: "國泰人壽", amount: "$92,000", status: "pending", paymentMethod: "銀行轉帳", issueDate: "2026/04/10", dueDate: "2026/04/30" },
  { id: "INV-2026-0407", workOrder: "WO-1240", customer: "李美玲", amount: "$12,800", status: "overdue", paymentMethod: "貨到付款", issueDate: "2026/04/02", dueDate: "2026/04/16" },
  { id: "INV-2026-0408", workOrder: "WO-1241", customer: "富邦銀行", amount: "$78,500", status: "paid", paymentMethod: "月結30天", issueDate: "2026/04/12", dueDate: "2026/05/02" },
];

const statusConfig = {
  overdue: { label: "逾期", textColor: "#EF4444", bgColor: "#FEE2E2" },
  pending: { label: "待付款", textColor: "#92400E", bgColor: "#FEF3C7" },
  paid: { label: "已付款", textColor: "#065F46", bgColor: "#D1FAE5" },
  disputed: { label: "爭議中", textColor: "#5B21B6", bgColor: "#EDE9FE" },
};

const columns = [
  { label: "發票編號", width: "w-[130px]" },
  { label: "工單連結", width: "w-[100px]" },
  { label: "客戶名稱", width: "w-[110px]" },
  { label: "金額", width: "w-[100px]" },
  { label: "付款狀態", width: "w-[80px]" },
  { label: "付款方式", width: "w-[90px]" },
  { label: "開立日期", width: "w-[90px]" },
  { label: "到期日", width: "w-[90px]" },
  { label: "操作", width: "flex-1" },
];

function ActionIcons({ status }: { status: Invoice["status"] }) {
  if (status === "paid") {
    return <Eye className="h-4 w-4 text-[var(--text-secondary)]" />;
  }

  if (status === "disputed") {
    return (
      <>
        <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
        <TriangleAlert className="h-4 w-4 text-[#F59E0B]" />
      </>
    );
  }

  return (
    <>
      <Eye className="h-4 w-4 text-[var(--text-secondary)]" />
      <RefreshCw className="h-4 w-4 text-[var(--primary)]" />
      <TriangleAlert className="h-4 w-4 text-[#F59E0B]" />
    </>
  );
}

export default function InvoicesTable() {
  return (
    <div className="flex flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        {columns.map((col) => (
          <div key={col.label} className={`flex items-center px-2 ${col.width}`}>
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Data Rows */}
      {invoices.map((inv) => {
        const badge = statusConfig[inv.status];
        const isOverdue = inv.status === "overdue";

        return (
          <div
            key={inv.id}
            className={`flex h-[48px] items-center border-b border-[var(--border)] px-8 ${
              isOverdue ? "border-l-[3px] border-l-[#EF4444] bg-[#FEF2F2]" : ""
            }`}
          >
            {/* Invoice ID */}
            <div className="flex w-[130px] items-center px-2">
              <span className="text-[13px] font-medium text-[var(--text-primary)]">
                {inv.id}
              </span>
            </div>

            {/* Work Order */}
            <div className="flex w-[100px] items-center px-2">
              <span className="text-[13px] font-medium text-[var(--primary)]">
                {inv.workOrder}
              </span>
            </div>

            {/* Customer */}
            <div className="flex w-[110px] items-center px-2">
              <span className="text-[13px] text-[var(--text-primary)]">
                {inv.customer}
              </span>
            </div>

            {/* Amount */}
            <div className="flex w-[100px] items-center px-2">
              <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                {inv.amount}
              </span>
            </div>

            {/* Status */}
            <div className="flex w-[80px] items-center px-2">
              <span
                className="rounded-full px-[10px] py-[3px] text-xs font-medium"
                style={{ color: badge.textColor, backgroundColor: badge.bgColor }}
              >
                {badge.label}
              </span>
            </div>

            {/* Payment Method */}
            <div className="flex w-[90px] items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {inv.paymentMethod}
              </span>
            </div>

            {/* Issue Date */}
            <div className="flex w-[90px] items-center px-2">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {inv.issueDate}
              </span>
            </div>

            {/* Due Date */}
            <div className="flex w-[90px] items-center px-2">
              <span className={`text-[13px] ${isOverdue ? "font-medium text-[#EF4444]" : "text-[var(--text-secondary)]"}`}>
                {inv.dueDate}
              </span>
            </div>

            {/* Actions */}
            <div className="flex flex-1 items-center gap-1 px-2">
              <ActionIcons status={inv.status} />
            </div>
          </div>
        );
      })}

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-[var(--border)] px-8 py-3">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 1-8 筆，共 24 筆
        </span>
        <div className="flex items-center gap-1">
          <button className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)]">
            <ChevronLeft className="h-4 w-4 text-[var(--text-secondary)]" />
          </button>
          {["1", "2", "3"].map((p, i) => (
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
