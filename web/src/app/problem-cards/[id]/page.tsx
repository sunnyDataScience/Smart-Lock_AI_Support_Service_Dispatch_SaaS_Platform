"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import FmeaDiagnosisCard from "@/components/problem-cards/FmeaDiagnosisCard";
import LinkedConversationCard from "@/components/problem-cards/LinkedConversationCard";
import ResolutionTimeline from "@/components/problem-cards/ResolutionTimeline";
import ProblemCardDetailSidebar from "@/components/problem-cards/ProblemCardDetailSidebar";

const deviceAttributes = [
  [
    { label: "品牌", value: "Yale" },
    { label: "型號", value: "YDM-4109" },
    { label: "症狀分類", value: "無法解鎖" },
  ],
  [
    { label: "錯誤代碼", value: "E3" },
    { label: "安裝日期", value: "2024-08-15" },
    { label: "韌體版本", value: "v2.1.3" },
  ],
];

export default function ProblemCardDetailPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        {/* Detail Header */}
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-5">
          <Link
            href="/problem-cards"
            className="text-[14px] font-medium text-[#2563EB]"
          >
            ← 返回問題卡片列表
          </Link>

          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 問題卡片 &gt; pc_a8f3d21e
          </span>

          <div className="flex w-full items-center gap-3">
            <span className="font-mono text-[14px] text-[var(--text-secondary)]">
              pc_a8f3d21e
            </span>
            <h1 className="flex-1 text-[24px] font-bold text-[var(--text-primary)]">
              Yale電子鎖YDM-4109密碼無法解鎖 按鍵有反應但輸入密碼後不會開鎖
            </h1>
          </div>

          {/* Warning Banner */}
          <div className="flex w-full items-center gap-[10px] rounded-lg bg-[#FEF3C7] px-4 py-3">
            <TriangleAlert className="h-5 w-5 flex-shrink-0 text-[#92400E]" />
            <span className="text-[14px] font-medium text-[#92400E]">
              此問題卡片已觸發熵值偵測，需人工確認診斷內容
            </span>
          </div>
        </div>

        {/* Detail Body */}
        <div className="flex flex-1 gap-6 overflow-auto px-8 py-6">
          {/* Main Content */}
          <div className="flex flex-1 flex-col gap-5">
            <FmeaDiagnosisCard />

            {/* Symptom Description */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
              <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
                症狀描述
              </h2>
              <p className="mt-4 text-[14px] leading-[1.6] text-[var(--text-primary)]">
                客戶反映Yale
                YDM-4109電子鎖在輸入正確密碼後按鍵有反應（發出嗶聲），但鎖具無法解鎖。嘗試多組備用密碼均無效。螢幕顯示錯誤代碼E3。電池於上個月更換為新品。
              </p>
            </div>

            {/* Device Attributes */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
              <h2 className="text-[18px] font-semibold text-[var(--text-primary)]">
                裝置屬性
              </h2>
              <div className="mt-4 flex gap-4">
                {deviceAttributes.map((col, colIdx) => (
                  <div key={colIdx} className="flex flex-1 flex-col gap-3">
                    {col.map((attr) => (
                      <div key={attr.label} className="flex flex-col gap-1">
                        <span className="text-[13px] font-medium text-[var(--text-secondary)]">
                          {attr.label}
                        </span>
                        <span className="text-[14px] font-medium text-[var(--text-primary)]">
                          {attr.value}
                        </span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <LinkedConversationCard />
            <ResolutionTimeline />
          </div>

          {/* Metadata Sidebar */}
          <ProblemCardDetailSidebar />
        </div>
      </div>
    </div>
  );
}
