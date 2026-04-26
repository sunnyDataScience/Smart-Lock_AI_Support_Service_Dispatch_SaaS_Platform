"use client";

import { useState } from "react";
import { Info, Search } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import WarrantyClaimsTable from "@/components/admin/WarrantyClaimsTable";

const statusTabs = ["全部", "有效", "寬限期", "已過期"];

export default function WarrantyClaimsPage() {
  const [activeTab, setActiveTab] = useState("全部");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-5 overflow-auto px-8 py-6">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            保固申請管理
          </h1>

          <div className="flex items-center gap-[10px] rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-4 py-3">
            <Info className="h-5 w-5 shrink-0 text-[#1D4ED8]" />
            <span className="text-[13px] leading-[1.5] text-[#1D4ED8]">
              保固起算日以「交屋日期」為準，非「入住日期」。此為系統核心規則，所有保固計算均依據此原則。
            </span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex overflow-hidden rounded-lg border border-[var(--border)]">
              {statusTabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-[13px] font-medium ${
                    activeTab === tab
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--bg-surface)] text-[var(--text-secondary)]"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="flex w-[300px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2">
              <Search className="h-4 w-4 text-[var(--text-secondary)]" />
              <input
                type="text"
                placeholder="搜尋案件編號、設備或客戶..."
                className="flex-1 bg-transparent text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
              />
            </div>
          </div>

          <WarrantyClaimsTable />
        </div>
      </div>
    </div>
  );
}
