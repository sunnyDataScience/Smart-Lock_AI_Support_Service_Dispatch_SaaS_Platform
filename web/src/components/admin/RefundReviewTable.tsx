"use client";

import Link from "next/link";

type StepColor = "#10B981" | "#F59E0B" | "#CBD5E1" | "#EF4444";

interface RefundRow {
  id: string;
  relatedOrder: string;
  amount: string;
  amountStyle: { color: string; fontWeight: string };
  reason: string;
  applicant: string;
  roleBadge: { label: string; textColor: string; bgColor: string };
  steps: [StepColor, StepColor, StepColor];
  stepLines: [StepColor, StepColor];
  sla: string;
  slaStyle: { color: string; fontWeight: string };
  status: { label: string; textColor: string; bgColor: string };
  actions: "review" | "completed" | "closed";
  isUrgent: boolean;
}

const rows: RefundRow[] = [
  {
    id: "RF-20260401",
    relatedOrder: "CS-10234",
    amount: "NT$ 158,000",
    amountStyle: { color: "#DC2626", fontWeight: "700" },
    reason: "設備瑕疵",
    applicant: "王小明",
    roleBadge: { label: "主管", textColor: "#1D4ED8", bgColor: "#DBEAFE" },
    steps: ["#10B981", "#F59E0B", "#CBD5E1"],
    stepLines: ["#CBD5E1", "#CBD5E1"],
    sla: "01:23:45",
    slaStyle: { color: "#DC2626", fontWeight: "700" },
    status: { label: "待審核", textColor: "#92400E", bgColor: "#FEF3C7" },
    actions: "review",
    isUrgent: true,
  },
  {
    id: "RF-20260402",
    relatedOrder: "CS-10198",
    amount: "NT$ 245,000",
    amountStyle: { color: "#DC2626", fontWeight: "700" },
    reason: "安裝失敗",
    applicant: "李佳琪",
    roleBadge: { label: "客服", textColor: "#7C3AED", bgColor: "#F3E8FF" },
    steps: ["#10B981", "#10B981", "#F59E0B"],
    stepLines: ["#CBD5E1", "#CBD5E1"],
    sla: "00:47:12",
    slaStyle: { color: "#DC2626", fontWeight: "700" },
    status: { label: "審核中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
    actions: "review",
    isUrgent: true,
  },
  {
    id: "RF-20260398",
    relatedOrder: "CS-10187",
    amount: "NT$ 8,500",
    amountStyle: { color: "var(--text-primary)", fontWeight: "400" },
    reason: "重複扣款",
    applicant: "張雅婷",
    roleBadge: { label: "財務", textColor: "#92400E", bgColor: "#FEF3C7" },
    steps: ["#10B981", "#CBD5E1", "#CBD5E1"],
    stepLines: ["#CBD5E1", "#CBD5E1"],
    sla: "05:12:30",
    slaStyle: { color: "#D97706", fontWeight: "600" },
    status: { label: "待審核", textColor: "#92400E", bgColor: "#FEF3C7" },
    actions: "review",
    isUrgent: false,
  },
  {
    id: "RF-20260395",
    relatedOrder: "CS-10156",
    amount: "NT$ 42,000",
    amountStyle: { color: "#D97706", fontWeight: "600" },
    reason: "合約終止",
    applicant: "陳志豪",
    roleBadge: { label: "業務", textColor: "#166534", bgColor: "#DCFCE7" },
    steps: ["#10B981", "#10B981", "#10B981"],
    stepLines: ["#10B981", "#10B981"],
    sla: "12:45:00",
    slaStyle: { color: "#059669", fontWeight: "400" },
    status: { label: "已核准", textColor: "#065F46", bgColor: "#D1FAE5" },
    actions: "completed",
    isUrgent: false,
  },
  {
    id: "RF-20260390",
    relatedOrder: "CS-10142",
    amount: "NT$ 75,000",
    amountStyle: { color: "#D97706", fontWeight: "600" },
    reason: "客訴退款",
    applicant: "林美玲",
    roleBadge: { label: "主管", textColor: "#1D4ED8", bgColor: "#DBEAFE" },
    steps: ["#10B981", "#F59E0B", "#CBD5E1"],
    stepLines: ["#CBD5E1", "#CBD5E1"],
    sla: "06:30:15",
    slaStyle: { color: "#D97706", fontWeight: "600" },
    status: { label: "審核中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
    actions: "review",
    isUrgent: false,
  },
  {
    id: "RF-20260388",
    relatedOrder: "CS-10130",
    amount: "NT$ 5,200",
    amountStyle: { color: "var(--text-primary)", fontWeight: "400" },
    reason: "功能異常",
    applicant: "黃建勳",
    roleBadge: { label: "技術", textColor: "#7C3AED", bgColor: "#F3E8FF" },
    steps: ["#10B981", "#10B981", "#EF4444"],
    stepLines: ["#10B981", "#EF4444"],
    sla: "24:10:00",
    slaStyle: { color: "#059669", fontWeight: "400" },
    status: { label: "已拒絕", textColor: "#991B1B", bgColor: "#FEE2E2" },
    actions: "closed",
    isUrgent: false,
  },
];

const columns = [
  { label: "退款編號", width: "w-[100px]" },
  { label: "關聯工單", width: "w-[90px]" },
  { label: "金額", width: "w-[90px]" },
  { label: "退款原因", width: "w-[90px]" },
  { label: "申請人", width: "w-[110px]" },
  { label: "審核步驟", width: "w-[110px]" },
  { label: "SLA剩餘", width: "w-[80px]" },
  { label: "狀態", width: "w-[70px]" },
  { label: "操作", width: "w-[130px]" },
];

function ReviewSteps({
  steps,
  lines,
}: {
  steps: [StepColor, StepColor, StepColor];
  lines: [StepColor, StepColor];
}) {
  return (
    <div className="flex items-center justify-center">
      <div
        className="h-[10px] w-[10px] rounded-full"
        style={{ backgroundColor: steps[0] }}
      />
      <div
        className="h-[2px] w-3"
        style={{ backgroundColor: lines[0] }}
      />
      <div
        className="h-[10px] w-[10px] rounded-full"
        style={{ backgroundColor: steps[1] }}
      />
      <div
        className="h-[2px] w-3"
        style={{ backgroundColor: lines[1] }}
      />
      <div
        className="h-[10px] w-[10px] rounded-full"
        style={{ backgroundColor: steps[2] }}
      />
    </div>
  );
}

export default function RefundReviewTable() {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      <div className="flex h-[44px] items-center rounded-t-lg bg-[#F1F5F9]">
        {columns.map((col) => (
          <div
            key={col.label}
            className={`flex items-center px-[10px] ${col.width}`}
          >
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {rows.map((row) => (
        <div
          key={row.id}
          className={`flex h-[52px] items-center border-b border-[var(--border)] last:border-b-0 ${
            row.isUrgent ? "bg-[#FEF2F2]" : ""
          }`}
        >
          <div className="flex w-[100px] items-center px-[10px]">
            <span className="font-mono text-xs text-[var(--text-primary)]">
              {row.id}
            </span>
          </div>

          <div className="flex w-[90px] items-center px-[10px]">
            <Link
              href={`/conversations/${row.relatedOrder}`}
              className="text-xs text-[#2563EB] hover:underline"
            >
              {row.relatedOrder}
            </Link>
          </div>

          <div className="flex w-[90px] items-center px-[10px]">
            <span
              className="text-xs"
              style={{
                color: row.amountStyle.color,
                fontWeight: row.amountStyle.fontWeight,
              }}
            >
              {row.amount}
            </span>
          </div>

          <div className="flex w-[90px] items-center px-[10px]">
            <span className="text-xs text-[var(--text-primary)]">
              {row.reason}
            </span>
          </div>

          <div className="flex w-[110px] flex-col justify-center gap-[2px] px-[10px]">
            <span className="text-xs text-[var(--text-primary)]">
              {row.applicant}
            </span>
            <span
              className="w-fit rounded px-[6px] py-[1px] text-[10px]"
              style={{
                color: row.roleBadge.textColor,
                backgroundColor: row.roleBadge.bgColor,
              }}
            >
              {row.roleBadge.label}
            </span>
          </div>

          <div className="flex w-[110px] items-center px-[10px]">
            <ReviewSteps steps={row.steps} lines={row.stepLines} />
          </div>

          <div className="flex w-[80px] items-center justify-center px-[10px]">
            <span
              className="text-xs"
              style={{
                color: row.slaStyle.color,
                fontWeight: row.slaStyle.fontWeight,
              }}
            >
              {row.sla}
            </span>
          </div>

          <div className="flex w-[70px] items-center justify-center px-[6px]">
            <span
              className="rounded-[10px] px-2 py-[3px] text-[11px] font-medium"
              style={{
                color: row.status.textColor,
                backgroundColor: row.status.bgColor,
              }}
            >
              {row.status.label}
            </span>
          </div>

          <div className="flex w-[130px] items-center justify-center gap-[6px] px-[6px]">
            {row.actions === "review" ? (
              <>
                <button className="rounded-md bg-[var(--primary)] px-3 py-1 text-[11px] font-medium text-white">
                  核准
                </button>
                <button className="rounded-md bg-[#EF4444] px-3 py-1 text-[11px] font-medium text-white">
                  拒絕
                </button>
              </>
            ) : (
              <span className="rounded-md bg-[#E2E8F0] px-3 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                {row.actions === "completed" ? "已完成" : "已結案"}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
