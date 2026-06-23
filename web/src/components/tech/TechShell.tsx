"use client";

import type { ReactNode } from "react";
import TechBottomNav from "./TechBottomNav";
import TechSidebar from "./TechSidebar";

interface Props {
  title?: string;
  /**
   * wide=true：內容區放寬到 1280px 給儀表板多欄網格（/home）。
   * 預設 false：內容置中於 680px 單欄，給既有列表/表單頁（pool / my-orders / account），
   * 桌面呈現為「側邊欄 + 聚焦內容欄」而非破版的全寬拉伸。
   */
  wide?: boolean;
  children: ReactNode;
}

// 響應式技師工作台外殼（2026-06-21 重構）：
//   - 手機 (<768px)：單欄全寬 + 底部 TechBottomNav（沿用手機優先版型）
//   - 桌面 (≥768px)：左側常駐 TechSidebar + 右側內容區（取代舊「固定 480px 置中欄」）
// 用純 CSS breakpoint（Tailwind md:）切換，不用 UA 偵測，避免 SSR hydration mismatch。
export default function TechShell({ title, wide = false, children }: Props) {
  return (
    <div className="flex min-h-screen w-full bg-[var(--bg-page)]">
      <TechSidebar />
      <div className="flex min-h-screen w-full flex-1 flex-col">
        {title && (
          <header className="sticky top-0 z-20 flex h-14 items-center border-b border-[var(--border)] bg-[var(--bg-surface)] px-4">
            <h1 className="text-[18px] font-semibold text-[var(--text-primary)]">{title}</h1>
          </header>
        )}
        <main className="flex-1 overflow-y-auto">
          <div
            className={`mx-auto w-full ${
              wide ? "md:max-w-[1280px]" : "min-h-full bg-[var(--bg-surface)] shadow-sm md:max-w-[680px]"
            }`}
          >
            {children}
          </div>
        </main>
        <TechBottomNav />
      </div>
    </div>
  );
}
