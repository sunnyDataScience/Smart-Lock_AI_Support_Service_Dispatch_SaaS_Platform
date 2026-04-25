"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";

type SopStatus = "draft" | "pending_review" | "approved" | "rejected";

interface SopDraftItem {
  id: string;
  title: string;
  conversationId: string;
  status: SopStatus;
  reviewer?: string;
  createdAt: string;
}

const statusConfig: Record<
  SopStatus,
  { label: string; bg: string; text: string }
> = {
  draft: {
    label: "草稿",
    bg: "#F1F5F9",
    text: "var(--text-disabled)",
  },
  pending_review: {
    label: "待審核",
    bg: "#FFFBEB",
    text: "var(--status-warning)",
  },
  approved: {
    label: "已核准",
    bg: "#ECFDF5",
    text: "var(--status-success)",
  },
  rejected: {
    label: "已拒絕",
    bg: "#FEF2F2",
    text: "var(--status-danger)",
  },
};

const drafts: SopDraftItem[] = [
  {
    id: "sop-001",
    title: "智能鎖密碼重置標準作業流程",
    conversationId: "CONV-2024-0892",
    status: "pending_review",
    reviewer: "陳技術長",
    createdAt: "2小時前",
  },
  {
    id: "sop-002",
    title: "指紋辨識模組清潔與校正 SOP",
    conversationId: "CONV-2024-0891",
    status: "pending_review",
    reviewer: "陳技術長",
    createdAt: "5小時前",
  },
  {
    id: "sop-003",
    title: "藍牙連線故障排除標準流程",
    conversationId: "CONV-2024-0887",
    status: "draft",
    createdAt: "1天前",
  },
  {
    id: "sop-004",
    title: "電池異常耗電診斷與更換流程",
    conversationId: "CONV-2024-0883",
    status: "approved",
    reviewer: "王小明",
    createdAt: "3天前",
  },
  {
    id: "sop-005",
    title: "門鎖馬達異音處理標準程序",
    conversationId: "CONV-2024-0879",
    status: "rejected",
    reviewer: "陳技術長",
    createdAt: "5天前",
  },
  {
    id: "sop-006",
    title: "App 連線異常排除步驟",
    conversationId: "CONV-2024-0875",
    status: "approved",
    reviewer: "王小明",
    createdAt: "1週前",
  },
  {
    id: "sop-007",
    title: "觸控面板無反應緊急處理 SOP",
    conversationId: "CONV-2024-0871",
    status: "draft",
    createdAt: "1週前",
  },
];

function StatusBadge({ status }: { status: SopStatus }) {
  const config = statusConfig[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-3 py-1 text-xs font-medium"
      style={{ backgroundColor: config.bg, color: config.text }}
    >
      {config.label}
    </span>
  );
}

export default function SopDraftsList() {
  return (
    <div className="flex flex-1 flex-col gap-4 px-8 py-6">
      {/* Filter Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]">
            排序：建立時間
            <ChevronRight className="h-[14px] w-[14px] rotate-90 text-[var(--text-secondary)]" />
          </button>
          <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-[var(--text-primary)]">
            狀態：全部
            <ChevronRight className="h-[14px] w-[14px] rotate-90 text-[var(--text-secondary)]" />
          </button>
        </div>
        <span className="text-[13px] text-[var(--text-secondary)]">
          共 {drafts.length} 筆草稿
        </span>
      </div>

      {/* Queue List */}
      <div className="flex-1 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
        {drafts.map((item, idx) => (
          <Link
            key={item.id}
            href={`/knowledge-base/sop-drafts/${item.id}`}
            className={`flex items-start justify-between px-5 py-4 hover:bg-[var(--bg-page)] ${
              idx < drafts.length - 1
                ? "border-b border-[var(--border)]"
                : ""
            }`}
          >
            <div className="flex flex-col gap-[6px]">
              <span className="text-[15px] font-semibold text-[var(--text-primary)]">
                {item.title}
              </span>
              <span className="text-[13px] text-[var(--primary)]">
                來源對話：{item.conversationId}
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                建立於 {item.createdAt}
              </span>
            </div>
            <div className="flex flex-col items-end gap-[6px]">
              <StatusBadge status={item.status} />
              {item.reviewer && (
                <span className="text-xs text-[var(--text-secondary)]">
                  審核者：{item.reviewer}
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-end">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 1-{drafts.length}，共 {drafts.length} 筆
        </span>
      </div>
    </div>
  );
}
