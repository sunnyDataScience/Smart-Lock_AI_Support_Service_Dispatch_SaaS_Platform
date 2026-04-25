"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import SopDraftsList from "@/components/knowledge-base/SopDraftsList";

const tabs = [
  { label: "案例庫", count: 128, href: "/knowledge-base" },
  { label: "產品手冊", count: 23, href: "/knowledge-base/manuals" },
  { label: "SOP 草稿", count: 7, href: "/knowledge-base/sop-drafts" },
];

export default function SopDraftsPage() {
  const pathname = usePathname();

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Page Header */}
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; SOP 草稿
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

        {/* SOP Drafts List */}
        <div className="flex-1 overflow-auto">
          <SopDraftsList />
        </div>
      </div>
    </div>
  );
}
