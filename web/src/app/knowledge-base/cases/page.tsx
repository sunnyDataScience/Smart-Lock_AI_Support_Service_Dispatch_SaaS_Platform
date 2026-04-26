"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Plus } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import CaseCardGrid from "@/components/knowledge-base/CaseCardGrid";

const tabs = [
  { label: "案例庫", count: 128, href: "/knowledge-base/cases" },
  { label: "產品手冊", count: 23, href: "/knowledge-base/manuals" },
  { label: "SOP 草稿", count: 7, href: "/knowledge-base/sop-drafts" },
];

type SearchMode = "keyword" | "semantic";

export default function CasesPage() {
  const pathname = usePathname();
  const [searchMode, setSearchMode] = useState<SearchMode>("semantic");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; 案例庫
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            知識庫管理
          </h1>

          <div className="flex">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`px-5 py-3 text-sm ${
                    isActive
                      ? "border-b-2 border-[var(--primary)] font-semibold text-[var(--primary)]"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {tab.label} ({tab.count})
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3">
            <Search className="h-[18px] w-[18px] text-[var(--text-secondary)]" />
            <input
              type="text"
              placeholder="搜尋案例（支援語意搜尋）..."
              className="h-10 flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
            />
          </div>

          <div className="flex h-9 overflow-hidden rounded-lg border border-[var(--border)]">
            <button
              onClick={() => setSearchMode("keyword")}
              className={`flex items-center justify-center px-[14px] text-sm ${
                searchMode === "keyword"
                  ? "bg-[var(--primary)] font-medium text-white"
                  : "bg-[var(--bg-surface)] font-medium text-[var(--text-secondary)]"
              }`}
            >
              關鍵字搜尋
            </button>
            <button
              onClick={() => setSearchMode("semantic")}
              className={`flex items-center justify-center px-[14px] text-sm ${
                searchMode === "semantic"
                  ? "bg-[var(--primary)] font-medium text-white"
                  : "bg-[var(--bg-surface)] font-medium text-[var(--text-secondary)]"
              }`}
            >
              語意搜尋
            </button>
          </div>

          <button className="flex h-10 items-center gap-2 rounded-lg bg-[var(--primary)] px-5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]">
            <Plus className="h-4 w-4" />
            新增案例
          </button>
        </div>

        <div className="flex-1 overflow-auto">
          <CaseCardGrid />
        </div>
      </div>
    </div>
  );
}
