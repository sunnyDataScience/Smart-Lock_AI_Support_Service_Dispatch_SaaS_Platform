"use client";

import Link from "next/link";
import {
  ArrowLeft,
  X,
  CircleCheck,
  CircleX,
  MessageSquare,
  Save,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

const sopData = {
  title: "Yale YDM-4109 離合器故障維修 SOP",
  status: "待審核" as const,
  steps: [
    {
      title: "確認故障現象",
      desc: "確認電子鎖螢幕顯示 E3 錯誤代碼，且輸入正確密碼後無法解鎖",
    },
    {
      title: "拆卸內面板",
      desc: "使用十字螺絲起子拆卸內面板四個固定螺絲",
    },
    {
      title: "檢查離合器模組",
      desc: "目視檢查離合器齒輪是否有明顯磨損或變形",
    },
    {
      title: "更換離合器組件",
      desc: "將新離合器對準安裝孔位，以順時針方向輕轉至卡入定位",
    },
    {
      title: "測試驗證",
      desc: "重新組裝內面板，輸入密碼測試解鎖功能是否正常",
    },
  ],
  source: {
    id: "CONV-A8F3D21E",
    summary: "陳小姐 - Yale YDM-4109 密碼無法解鎖",
  },
  models: ["Yale", "YDM-4109", "YDM-7116"],
  timeline: [
    {
      action: "要求修改",
      color: "#F59E0B",
      textColor: "#D97706",
      detail:
        "步驟3需補充磨損程度判斷標準，步驟5需增加客戶簽名確認流程",
      meta: "王小明 · 2026-04-22 10:30",
    },
    {
      action: "AI 自動產生草稿",
      color: "#94A3B8",
      textColor: "#64748B",
      meta: "系統 · 2026-04-22 09:15",
    },
  ],
};

export default function SopReviewPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Review Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/knowledge-base/sop-drafts"
              className="flex items-center gap-[6px] text-sm text-[var(--primary)]"
            >
              <ArrowLeft className="h-4 w-4" />
              返回 SOP 草稿列表
            </Link>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">
              {sopData.title}
            </h1>
            <span className="rounded-full bg-[var(--status-warning)] px-3 py-1 text-xs font-semibold text-[#92400E]">
              {sopData.status}
            </span>
          </div>
          <Link
            href="/knowledge-base/sop-drafts"
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-[var(--bg-page)]"
          >
            <X className="h-5 w-5 text-[var(--text-secondary)]" />
          </Link>
        </div>

        {/* Two-Column Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: AI Content */}
          <div className="flex-1 overflow-auto border-r border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex flex-col gap-5">
              <h2 className="text-[22px] font-bold text-[var(--text-primary)]">
                {sopData.title}
              </h2>

              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                SOP 步驟
              </h3>

              {/* Steps */}
              <div className="flex flex-col gap-4">
                {sopData.steps.map((step, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-xs font-bold text-white">
                      {idx + 1}
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-sm font-semibold text-[var(--text-primary)]">
                        {step.title}
                      </span>
                      <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
                        {step.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Source Card */}
              <div className="flex flex-col gap-2 rounded-lg bg-[#EFF6FF] p-4">
                <span className="text-xs font-semibold text-[var(--text-secondary)]">
                  來源對話
                </span>
                <span className="text-sm font-medium text-[var(--primary)]">
                  {sopData.source.id}
                </span>
                <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {sopData.source.summary}
                </p>
              </div>

              {/* Applicable Models */}
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold text-[var(--text-secondary)]">
                  適用機型
                </span>
                <div className="flex gap-2">
                  {sopData.models.map((model) => (
                    <span
                      key={model}
                      className="rounded-md bg-[var(--primary-light)] px-[10px] py-1 text-xs font-medium text-[var(--primary)]"
                    >
                      {model}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Right: Review Tools */}
          <div className="flex w-[42%] flex-col gap-5 overflow-auto bg-[var(--bg-page)] p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">
              審核工具
            </h3>
            <p className="text-[13px] text-[var(--text-secondary)]">
              請仔細閱讀左側 AI 產生的 SOP 內容，並提供審核意見
            </p>

            {/* Notes */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-[var(--text-primary)]">
                審核意見 *
              </label>
              <textarea
                placeholder="輸入審核意見，支援 Markdown 格式..."
                className="h-[140px] w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-3 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)] focus:border-[var(--border-focus)]"
              />
              <span className="text-[11px] text-[var(--text-disabled)]">
                拒絕或要求修改時必須填寫審核意見
              </span>
            </div>

            {/* Review History */}
            <div className="flex flex-col gap-3">
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                審核歷程
              </span>
              <div className="flex flex-col">
                {sopData.timeline.map((item, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div
                        className="h-[10px] w-[10px] shrink-0 rounded-full"
                        style={{ backgroundColor: item.color }}
                      />
                      {idx < sopData.timeline.length - 1 && (
                        <div className="w-[2px] flex-1 bg-[var(--border)]" />
                      )}
                    </div>
                    <div className="flex flex-col gap-1 pb-4">
                      <span
                        className="text-[13px] font-semibold"
                        style={{ color: item.textColor }}
                      >
                        {item.action}
                      </span>
                      {item.detail && (
                        <p className="text-xs text-[var(--text-secondary)]">
                          {item.detail}
                        </p>
                      )}
                      <span className="text-[11px] text-[var(--text-disabled)]">
                        {item.meta}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Divider */}
            <div className="h-px bg-[var(--border)]" />

            {/* Action Buttons */}
            <div className="flex flex-col gap-[10px]">
              <button className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-[var(--status-success)] text-sm font-semibold text-white hover:opacity-90">
                <CircleCheck className="h-[18px] w-[18px]" />
                核准並發布
              </button>
              <button className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-[var(--status-danger)] text-sm font-semibold text-white hover:opacity-90">
                <CircleX className="h-[18px] w-[18px]" />
                拒絕
              </button>
              <button className="flex h-[42px] items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-page)]">
                <MessageSquare className="h-[18px] w-[18px]" />
                要求修改
              </button>
              <button className="flex h-[42px] items-center justify-center gap-2 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--border)]">
                <Save className="h-[18px] w-[18px]" />
                暫存審核意見
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
