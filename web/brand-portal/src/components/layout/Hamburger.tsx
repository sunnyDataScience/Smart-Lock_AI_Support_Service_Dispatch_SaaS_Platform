"use client";

import { Menu, X } from "lucide-react";
import { useSidebar } from "./SidebarContext";
import { useTranslations } from "@/components/i18n/LocaleProvider";

/**
 * Hamburger — 行動版 sidebar drawer 開關按鈕（floating 模式）
 *
 * 為什麼 floating（fixed 在 viewport 左上）：
 * - 不是所有 page 都用 <Header /> 元件（work-orders、admin/* 自刻 header）
 * - 改 Header 內掛會錯過半數 page
 * - 改 floating 後，Sidebar 內部 render 即可，所有 page 自動有
 *
 * 桌機（md+）md:hidden 隱藏；行動版 fixed top-3 left-3。
 * z-50 確保在 Sidebar drawer (z-40) 與 backdrop (z-30) 之上，
 * 即使 drawer 開著也能用同一個按鈕關閉（icon 變 X）。
 */

export default function Hamburger() {
  const { isOpen, toggle } = useSidebar();
  const t = useTranslations("sidebar");

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isOpen ? t("closeNav") : t("openNav")}
      aria-expanded={isOpen}
      aria-controls="sidebar-drawer"
      className="md:hidden fixed left-2 top-2 z-50 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/85 text-[var(--text-secondary)] shadow-sm backdrop-blur-sm transition hover:bg-white hover:text-[var(--text-primary)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1 active:scale-95"
    >
      {isOpen ? (
        <X className="h-5 w-5" aria-hidden="true" />
      ) : (
        <Menu className="h-5 w-5" aria-hidden="true" />
      )}
    </button>
  );
}
