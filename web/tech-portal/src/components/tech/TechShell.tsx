"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import TechBottomNav from "./TechBottomNav";
import TechSidebar from "./TechSidebar";

interface Props {
  /** 主標題。無 kicker 時 18px;有 kicker 時 15px(kicker 11px 在上,兩行同塞 56px bar)。 */
  title?: string;
  /** 標題上方小字(如工單編號 #AB12CD34)。 */
  kicker?: string;
  /** 有值 → bar 左側顯示返回鈕,點擊 router.push(backHref)。 */
  backHref?: string;
  /** 標題右側 inline 資訊(件數 chip / 狀態 badge / realtime 指示)。 */
  meta?: ReactNode;
  /** bar 右側動作區(refresh 等;慣例 h-9 w-9 rounded-full icon 鈕)。 */
  actions?: ReactNode;
  /** 頁首第二列(分頁 tab 列),寬度與內容欄對齊。 */
  tabs?: ReactNode;
  /**
   * wide=true：內容區放寬到 1280px 給儀表板多欄網格（/home /pool /my-orders /account）。
   * 預設 false：內容置中於 680px 白卡單欄（工單詳情/表單頁），有底色+陰影的
   * 卡片外觀屬刻意設計。
   */
  wide?: boolean;
  children: ReactNode;
}

// 響應式技師工作台外殼（2026-06-21 重構；2026-07-07 頁首統一）：
//   - 手機 (<768px)：單欄全寬 + 底部 TechBottomNav
//   - 桌面 (≥768px)：左側常駐 TechSidebar + 右側內容區
//
// 【頁首一致性規格】全師傅端唯一頁首來源 —— 各頁不再自組 header:
//   - bar 固定 h-14(56px)、sticky top-0、滿寬 border-b + bg-surface
//     (背景貼齊側欄到視窗右緣,內文對齊內容欄寬;修大螢幕「浮動白條」)
//   - 結構:[返回鈕?] [kicker?+標題(truncate)] [meta?] ・・・ [actions?]
//   - 第二列 tabs?(my-orders 分頁列)同寬對齊
export default function TechShell({
  title,
  kicker,
  backHref,
  meta,
  actions,
  tabs,
  wide = false,
  children,
}: Props) {
  const router = useRouter();
  const columnWidth = wide ? "md:max-w-[1280px]" : "md:max-w-[680px]";
  const hasBar = Boolean(title || backHref || actions);
  return (
    <div className="tech-soft flex min-h-screen w-full bg-[var(--bg-page)]">
      <TechSidebar />
      <div className="flex min-h-screen w-full min-w-0 flex-1 flex-col">
        {hasBar && (
          <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg-surface)]">
            <div
              className={`mx-auto flex h-14 w-full items-center gap-2 px-4 md:px-6 ${columnWidth}`}
            >
              {backHref && (
                <button
                  type="button"
                  onClick={() => router.push(backHref)}
                  className="-ml-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--bg-page)]"
                  aria-label="返回"
                >
                  <ArrowLeft className="h-5 w-5" />
                </button>
              )}
              <div className="flex min-w-0 flex-col justify-center">
                {kicker && (
                  <span className="truncate text-[11px] leading-tight text-[var(--text-disabled)]">
                    {kicker}
                  </span>
                )}
                {title && (
                  <h1
                    className={`truncate font-semibold text-[var(--text-primary)] ${
                      kicker ? "text-[15px] leading-tight" : "text-[18px]"
                    }`}
                  >
                    {title}
                  </h1>
                )}
              </div>
              {meta && <div className="flex min-w-0 items-center gap-1.5">{meta}</div>}
              {actions && (
                <div className="ml-auto flex shrink-0 items-center gap-1.5">{actions}</div>
              )}
            </div>
            {tabs && <div className={`mx-auto w-full ${columnWidth}`}>{tabs}</div>}
          </header>
        )}
        {/* WCAG 2.4.1 Bypass Blocks：SkipLink.tsx 的 href="#main-content" 需要這個
            錨點才跳得到。tabIndex={-1} 不可省——沒有它 <main> 不可聚焦，skip link
            只會捲動而不移動鍵盤焦點，等於沒作用。掛在 shell 而非逐頁，一次覆蓋
            全部師傅端頁面（brand-portal 是逐頁掛，只有 3 頁有）。 */}
        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto">
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
