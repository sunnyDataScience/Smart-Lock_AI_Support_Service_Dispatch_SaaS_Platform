"use client";

import { Download, Search, ChevronDown } from "lucide-react";
import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import ConversationsTable from "@/components/conversations/ConversationsTable";

const tabs = [
  { label: "全部", count: 156 },
  { label: "待處理", count: 23 },
  { label: "收集中", count: 45 },
  { label: "處理中", count: 38 },
  { label: "已解決", count: 42 },
  { label: "已升級", count: 8 },
];

export default function ConversationsPage() {
  const [activeTab, setActiveTab] = useState("全部");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-[24px] font-semibold text-[#18181B]">
              對話管理
            </h1>
            <button className="flex items-center gap-2 rounded-lg border-[1.5px] border-[#E4E4E7] px-4 py-2">
              <Download className="h-4 w-4 text-[#71717A]" />
              <span className="text-[14px] font-semibold text-[#71717A]">
                匯出
              </span>
            </button>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex">
              {tabs.map((tab) => (
                <button
                  key={tab.label}
                  onClick={() => setActiveTab(tab.label)}
                  className={`flex items-center gap-[6px] px-3 py-[10px] text-[14px] ${
                    activeTab === tab.label
                      ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                      : "font-medium text-[#71717A]"
                  }`}
                >
                  <span>{tab.label}</span>
                  <span
                    className={`text-[14px] ${
                      activeTab === tab.label
                        ? "font-medium text-[var(--primary)]"
                        : "text-[#A1A1AA]"
                    }`}
                  >
                    {tab.count}
                  </span>
                </button>
              ))}
            </div>

            <div className="flex w-[280px] items-center gap-2 rounded-lg border-[1.5px] border-[#E4E4E7] px-3 py-2">
              <Search className="h-4 w-4 text-[#A1A1AA]" />
              <input
                type="text"
                placeholder="搜尋客戶名稱、對話內容..."
                className="flex-1 bg-transparent text-[14px] text-[#18181B] outline-none placeholder:text-[#A1A1AA]"
              />
            </div>

            <button className="flex items-center gap-2 rounded-lg border-[1.5px] border-[#E4E4E7] px-3 py-2">
              <span className="text-[14px] font-medium text-[#18181B]">
                全部頻道
              </span>
              <ChevronDown className="h-4 w-4 text-[#71717A]" />
            </button>

            <button className="flex items-center gap-2 rounded-lg border-[1.5px] border-[#E4E4E7] px-3 py-2">
              <span className="text-[14px] font-medium text-[#18181B]">
                最新訊息優先
              </span>
              <ChevronDown className="h-4 w-4 text-[#71717A]" />
            </button>
          </div>
        </div>

        <main className="flex-1 overflow-auto px-8 py-6">
          <ConversationsTable />
        </main>
      </div>
    </div>
  );
}
