"use client";

import {
  ChevronLeft,
  TriangleAlert,
  Check,
  EllipsisVertical,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import ChatTimeline from "@/components/conversations/ChatTimeline";
import ConversationInfoSidebar from "@/components/conversations/ConversationInfoSidebar";

export default function ConversationDetailPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Detail Header */}
        <header className="flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-6">
          <div className="flex items-center gap-3">
            <Link
              href="/conversations"
              className="flex items-center gap-[6px] rounded-md px-[10px] py-[6px] text-[13px] font-medium text-[var(--text-secondary)]"
            >
              <ChevronLeft className="h-4 w-4" />
              返回列表
            </Link>

            <div className="h-6 w-px bg-[var(--border)]" />

            <span className="font-mono text-[13px] font-medium text-[var(--text-secondary)]">
              CONV-A8F3D21E
            </span>

            <span className="flex items-center gap-1 rounded-full bg-[var(--primary-light)] px-[10px] py-[3px]">
              <span className="h-[6px] w-[6px] rounded-full bg-[var(--primary)]" />
              <span className="text-[12px] font-medium text-[var(--primary)]">
                收集中
              </span>
            </span>

            <span className="rounded-full border border-[#06C755] px-[10px] py-[3px] text-[12px] font-semibold text-[#06C755]">
              LINE
            </span>

            <span className="text-[16px] font-bold text-[var(--text-primary)]">
              陳小姐
            </span>

            <span className="text-[12px] text-[var(--text-secondary)]">
              對話持續 3 分鐘
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-[6px]">
              <span className="h-2 w-2 rounded-full bg-[var(--success)]" />
              <span className="text-[11px] text-[var(--text-secondary)]">
                即時連線
              </span>
            </div>

            <div className="h-6 w-px bg-[var(--border)]" />

            <button className="flex items-center gap-[6px] rounded-lg border border-[#FECACA] px-4 py-2">
              <TriangleAlert className="h-[14px] w-[14px] text-[var(--error)]" />
              <span className="text-[13px] font-semibold text-[var(--error)]">
                升級處理
              </span>
            </button>

            <button className="flex items-center gap-[6px] rounded-lg bg-[var(--primary)] px-4 py-2">
              <Check className="h-[14px] w-[14px] text-white" />
              <span className="text-[13px] font-semibold text-white">
                標記已解決
              </span>
            </button>

            <button className="flex items-center justify-center rounded-md border border-[var(--border)] p-2">
              <EllipsisVertical className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>
          </div>
        </header>

        {/* Body: Chat + Info Sidebar */}
        <div className="flex flex-1 overflow-hidden">
          <ChatTimeline />
          <ConversationInfoSidebar />
        </div>
      </div>
    </div>
  );
}
