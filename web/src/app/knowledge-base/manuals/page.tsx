"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CloudUpload } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";
import ManualsTable from "@/components/knowledge-base/ManualsTable";

const tabs = [
  { label: "案例庫", count: 128, href: "/knowledge-base" },
  { label: "產品手冊", count: 23, href: "/knowledge-base/manuals" },
  { label: "SOP 草稿", count: 7, href: "/knowledge-base/sop-drafts" },
];

export default function ManualsPage() {
  const pathname = usePathname();

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header */}
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; 產品手冊
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            知識庫管理
          </h1>

          {/* Tab Bar */}
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

        {/* Body */}
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {/* Upload Dropzone */}
          <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-[var(--border)] bg-[var(--bg-page)] px-10 py-10">
            <CloudUpload className="h-12 w-12 text-[var(--text-secondary)]" />
            <div className="flex items-center gap-1">
              <span className="text-sm text-[var(--text-secondary)]">
                拖放 PDF 檔案至此，或
              </span>
              <button className="text-sm font-semibold text-[var(--primary)]">
                點擊上傳
              </button>
            </div>
            <span className="text-xs text-[var(--text-disabled)]">
              支援格式：PDF，單檔上限 50MB
            </span>
          </div>

          {/* File Table */}
          <ManualsTable />

          {/* Pagination */}
          <div className="flex items-center justify-end">
            <span className="text-[13px] text-[var(--text-secondary)]">
              顯示 1-6，共 23 筆
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
