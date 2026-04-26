"use client";

import Link from "next/link";
import { ChevronRight, Ellipsis } from "lucide-react";

interface DispatchRow {
  id: string;
  attempt: 1 | 2 | 3;
  techName: string;
  techColor: string;
  matchScore: number;
  reason: string;
  remaining: string;
  remainingColor: "default" | "warning" | "critical";
  createdAt: string;
  isStuck: boolean;
}

const attemptBadge: Record<
  1 | 2 | 3,
  { label: string; bg: string; text: string }
> = {
  1: { label: "第 1 次", bg: "#DBEAFE", text: "#2563EB" },
  2: { label: "第 2 次", bg: "#FEF3C7", text: "#D97706" },
  3: { label: "第 3 次", bg: "#FEE2E2", text: "#DC2626" },
};

function scoreColor(score: number): string {
  if (score >= 80) return "#10B981";
  if (score >= 60) return "#3B82F6";
  if (score >= 40) return "#F59E0B";
  return "#EF4444";
}

const remainingStyles: Record<string, string> = {
  default: "text-[var(--text-primary)] font-medium",
  warning: "text-[#D97706] font-medium",
  critical: "text-[#DC2626] font-bold",
};

const rows: DispatchRow[] = [
  {
    id: "WO-20260425-0087",
    attempt: 3,
    techName: "王大明",
    techColor: "#2563EB",
    matchScore: 37,
    reason: "距離太遠，無法前往",
    remaining: "已逾時 8min",
    remainingColor: "critical",
    createdAt: "04-25 09:15",
    isStuck: true,
  },
  {
    id: "WO-20260425-0093",
    attempt: 2,
    techName: "林美玲",
    techColor: "#8B5CF6",
    matchScore: 68,
    reason: "行程衝突",
    remaining: "12:45",
    remainingColor: "warning",
    createdAt: "04-25 10:30",
    isStuck: false,
  },
  {
    id: "WO-20260425-0078",
    attempt: 2,
    techName: "張志豪",
    techColor: "#10B981",
    matchScore: 78,
    reason: "技能不符，無該品牌經驗",
    remaining: "08:22",
    remainingColor: "default",
    createdAt: "04-25 11:05",
    isStuck: false,
  },
  {
    id: "WO-20260424-0156",
    attempt: 1,
    techName: "李建華",
    techColor: "#F59E0B",
    matchScore: 89,
    reason: "—",
    remaining: "14:15",
    remainingColor: "default",
    createdAt: "04-25 14:02",
    isStuck: false,
  },
  {
    id: "WO-20260424-0142",
    attempt: 3,
    techName: "陳志偉",
    techColor: "#6366F1",
    matchScore: 45,
    reason: "超出服務範圍",
    remaining: "已逾時 3min",
    remainingColor: "critical",
    createdAt: "04-24 16:40",
    isStuck: true,
  },
  {
    id: "WO-20260425-0101",
    attempt: 2,
    techName: "黃淑芬",
    techColor: "#EC4899",
    matchScore: 58,
    reason: "當天已排滿",
    remaining: "06:33",
    remainingColor: "warning",
    createdAt: "04-25 13:20",
    isStuck: false,
  },
];

const columns = [
  { label: "", width: "w-10" },
  { label: "工單編號", width: "w-[140px]" },
  { label: "派工次數", width: "w-20" },
  { label: "當前技師", width: "w-[140px]" },
  { label: "媒合分數", width: "w-[120px]" },
  { label: "拒單原因", width: "flex-1" },
  { label: "剩餘時間", width: "w-[100px]" },
  { label: "建立時間", width: "w-[130px]" },
  { label: "操作", width: "w-20" },
];

export default function DispatchQueueTable() {
  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
        <div className="flex items-center bg-[#F8FAFC] px-4 py-3">
          {columns.map((col) => (
            <span
              key={col.label || "expand"}
              className={`${col.width} shrink-0 text-xs font-semibold text-[var(--text-secondary)]`}
            >
              {col.label}
            </span>
          ))}
        </div>

        {rows.map((row) => {
          const badge = attemptBadge[row.attempt];
          const color = scoreColor(row.matchScore);
          const barWidth = Math.round((row.matchScore / 100) * 60);

          return (
            <div
              key={row.id}
              className={`flex items-center border-t border-[var(--border)] px-4 py-3 hover:bg-[#EFF6FF] ${
                row.isStuck ? "border-l-4 border-l-[#EF4444] bg-[#FEF2F2]" : ""
              }`}
            >
              <div className="flex w-10 shrink-0 items-center justify-center">
                <ChevronRight className="h-4 w-4 text-[var(--text-secondary)]" />
              </div>

              <Link
                href={`/work-orders/${row.id}`}
                className="w-[140px] shrink-0 font-mono text-[13px] font-medium text-[var(--primary)]"
              >
                {row.id}
              </Link>

              <div className="flex w-20 shrink-0 items-center">
                <span
                  className="rounded px-2 py-[2px] text-xs font-semibold"
                  style={{ backgroundColor: badge.bg, color: badge.text }}
                >
                  {badge.label}
                </span>
              </div>

              <div className="flex w-[140px] shrink-0 items-center gap-2">
                <div
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
                  style={{ backgroundColor: row.techColor }}
                >
                  {row.techName[0]}
                </div>
                <span className="text-[13px] text-[var(--text-primary)]">
                  {row.techName}
                </span>
              </div>

              <div className="flex w-[120px] shrink-0 items-center gap-2">
                <div className="h-[6px] w-[60px] overflow-hidden rounded-full bg-[#E2E8F0]">
                  <div
                    className="h-full rounded-full"
                    style={{ width: barWidth, backgroundColor: color }}
                  />
                </div>
                <span
                  className="text-[13px] font-semibold"
                  style={{ color }}
                >
                  {row.matchScore}
                </span>
              </div>

              <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--text-secondary)]">
                {row.reason}
              </span>

              <span
                className={`w-[100px] shrink-0 text-[13px] ${remainingStyles[row.remainingColor]}`}
              >
                {row.remaining}
              </span>

              <span className="w-[130px] shrink-0 text-[13px] text-[var(--text-secondary)]">
                {row.createdAt}
              </span>

              <div className="flex w-20 shrink-0 items-center">
                {row.isStuck ? (
                  <button className="rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-semibold text-white hover:opacity-90">
                    介入
                  </button>
                ) : (
                  <button className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-[var(--bg-page)]">
                    <Ellipsis className="h-5 w-5 text-[var(--text-secondary)]" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between px-4">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 1-6，共 13 筆
        </span>
        <div className="flex items-center gap-1">
          {[1, 2, 3].map((page) => (
            <button
              key={page}
              className={`flex h-8 w-8 items-center justify-center rounded-md text-[13px] ${
                page === 1
                  ? "bg-[var(--primary)] font-semibold text-white"
                  : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)]"
              }`}
            >
              {page}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
