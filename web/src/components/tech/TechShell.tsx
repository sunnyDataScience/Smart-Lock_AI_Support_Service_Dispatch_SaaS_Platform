"use client";

import type { ReactNode } from "react";
import TechBottomNav from "./TechBottomNav";
import TechSidebar from "./TechSidebar";

interface Props {
  title?: string;
  /**
   * header：頁首列（標題/重新整理/分頁 tab 等）。
   * CR：RWD 大螢幕跑版修正（2026-07-06）—— 原本各頁把 sticky 頁首放在「置中內容欄」
   * 裡，>1520px 時內容欄兩側出現灰帶、白色頁首跟著浮在畫面中間、與側欄斷開（業主
   * 回報「螢幕大一點就跑掉」）。改由 shell 統一渲染：**背景橫跨整個 main 滿寬**、
   * 內文用與內容欄相同的 max-width 對齊 —— 頁框錨定、內容聚焦，兩者兼得。
   */
  header?: ReactNode;
  /**
   * wide=true：內容區放寬到 1280px 給儀表板多欄網格（/home /pool /my-orders /account）。
   * 預設 false：內容置中於 680px 白卡單欄（工單詳情/表單頁），有底色+陰影的
   * 卡片外觀屬刻意設計。
   */
  wide?: boolean;
  children: ReactNode;
}

// 響應式技師工作台外殼（2026-06-21 重構）：
//   - 手機 (<768px)：單欄全寬 + 底部 TechBottomNav（沿用手機優先版型）
//   - 桌面 (≥768px)：左側常駐 TechSidebar + 右側內容區（取代舊「固定 480px 置中欄」）
// 用純 CSS breakpoint（Tailwind md:）切換，不用 UA 偵測，避免 SSR hydration mismatch。
export default function TechShell({ title, header, wide = false, children }: Props) {
  const columnWidth = wide ? "md:max-w-[1280px]" : "md:max-w-[680px]";
  return (
    <div className="tech-soft flex min-h-screen w-full bg-[var(--bg-page)]">
      <TechSidebar />
      <div className="flex min-h-screen w-full min-w-0 flex-1 flex-col">
        {header ? (
          // 滿寬頁首帶（bg/border 貼齊側欄到視窗右緣）；內文對齊內容欄寬度
          <header className="z-20 border-b border-[var(--border)] bg-[var(--bg-surface)]">
            <div className={`mx-auto w-full ${columnWidth}`}>{header}</div>
          </header>
        ) : title ? (
          <header className="sticky top-0 z-20 flex h-14 items-center border-b border-[var(--border)] bg-[var(--bg-surface)] px-4">
            <h1 className="text-[18px] font-semibold text-[var(--text-primary)]">{title}</h1>
          </header>
        ) : null}
        <main className="flex-1 overflow-y-auto">
          <div
            className={`mx-auto w-full ${
              wide ? columnWidth : `min-h-full bg-[var(--bg-surface)] shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))] ${columnWidth}`
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
