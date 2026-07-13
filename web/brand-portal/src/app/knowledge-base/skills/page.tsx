"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import SkillsTable from "@/components/knowledge-base/SkillsTable";
import { useKbCounts } from "@/hooks/useKbCounts";
import { friendlyError } from "@/lib/apiError";
import { listSkills, type SkillSummary } from "@/lib/skills-api";

const tabs = [
  { label: "案例庫", href: "/knowledge-base/cases", key: "cases" as const },
  { label: "產品手冊", href: "/knowledge-base/manuals", key: "manuals" as const },
  { label: "SOP 草稿", href: "/knowledge-base/sop-drafts", key: "sopDrafts" as const },
  { label: "AI 技能", href: "/knowledge-base/skills", key: "skills" as const },
];

export default function SkillsPage() {
  const pathname = usePathname();
  const kbCounts = useKbCounts();
  const [items, setItems] = useState<SkillSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 抓列表：可重複呼叫（初次載入 + 回到本頁時刷新）。不重置 loading，避免刷新時整表閃「載入中」。
  const fetchSkills = useCallback(async () => {
    try {
      const rows = await listSkills();
      setItems(rows);
      setError(null);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // 初次載入 + 視窗重新聚焦 / 分頁重新可見時刷新。
  // 修 CR-0167 UAT 回報：從編輯頁「發佈」後以瀏覽器上一頁（bfcache）回列表，
  // useEffect(mount-only) 不重跑 → 狀態顯示 stale。監聽 focus / visibilitychange
  // 涵蓋瀏覽器返回、切分頁、bfcache 還原，不論以何種方式回到本頁都取最新發佈狀態。
  useEffect(() => {
    void fetchSkills();
    const refetch = () => {
      if (document.visibilityState !== "hidden") void fetchSkills();
    };
    window.addEventListener("focus", refetch);
    document.addEventListener("visibilitychange", refetch);
    return () => {
      window.removeEventListener("focus", refetch);
      document.removeEventListener("visibilitychange", refetch);
    };
  }, [fetchSkills]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 pt-5">
          <span className="text-[13px] text-[var(--text-secondary)]">
            首頁 &gt; 知識庫 &gt; AI 技能
          </span>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">知識庫管理</h1>

          <div className="flex">
            {tabs.map((tab) => {
              const isActive = tab.href === pathname;
              const count = kbCounts[tab.key] ?? "—";
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
                  {tab.label} ({count})
                </Link>
              );
            })}
          </div>
        </div>

        {/* 說明橫幅：技能是 AI 回答依據，發佈後 ≤60 秒生效、不需重佈 */}
        <div className="mx-4 mt-4 rounded-lg border border-[var(--primary)]/25 bg-[var(--primary-light)]/40 px-4 py-3 text-[13px] leading-relaxed text-[var(--text-secondary)] md:mx-8">
          <span className="font-semibold text-[var(--text-primary)]">AI 技能</span>
          {" 是客服 AI 回答時的知識與話術依據。編輯後存為草稿，由管理員發佈；"}
          <span className="font-medium text-[var(--text-primary)]">發佈後約 60 秒內</span>
          {" 自動生效於 LINE 客服，無需重新部署。每次發佈都保留版本，可隨時回滾。"}
        </div>

        {error && (
          <div className="mx-4 mt-4 rounded-lg border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)] md:mx-8">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <SkillsTable items={items} loading={loading} />
        </div>
      </div>
    </div>
  );
}
