"use client";

import { Search } from "lucide-react";
import NotificationBell from "./NotificationBell";
import ThemeToggle from "@/components/theme/ThemeToggle";
import LocaleToggle from "@/components/i18n/LocaleToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";

interface HeaderProps {
  title: string;
  subtitle?: string;
}

/**
 * 注意：mobile drawer 開關按鈕 (Hamburger) 是 floating，由 Sidebar 元件
 * 內部 render，不在 Header 內。所有 page 不論用不用 <Header /> 都自動有。
 */
export default function Header({ title, subtitle }: HeaderProps) {
  const t = useTranslations("header");
  return (
    <header className="flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-2 md:gap-4">
        {/* mobile 留空間給 floating Hamburger，避免標題被遮住 */}
        <div className="md:hidden h-10 w-10 shrink-0" aria-hidden="true" />
        <h1 className="truncate text-[20px] font-semibold tracking-tight text-[var(--text-primary)] md:text-[24px]">
          {title}
        </h1>
        {subtitle && (
          <span className="hidden text-[14px] text-[var(--text-secondary)] md:inline">
            {subtitle}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        {/* 搜尋框 — 小螢幕完全隱藏（避免擠壓 hamburger / title）；
         * sm 起寬度漸進 200 → 280 → 320 */}
        <label
          htmlFor="header-global-search"
          className="hidden items-center gap-2 rounded-xl border border-[var(--border)] px-3 py-0 focus-within:border-[var(--border-focus)] focus-within:ring-2 focus-within:ring-[var(--border-focus)] focus-within:ring-offset-1 sm:flex sm:w-[200px] md:w-[280px] lg:w-[320px]"
        >
          <Search
            className="h-[18px] w-[18px] text-[var(--text-disabled)]"
            aria-hidden="true"
          />
          <span className="sr-only">{t("searchSrLabel")}</span>
          <input
            id="header-global-search"
            type="search"
            placeholder={t("searchPlaceholder")}
            aria-label={t("searchLabel")}
            className="h-10 flex-1 bg-transparent text-[14px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-disabled)]"
          />
        </label>

        <LocaleToggle />
        <ThemeToggle />
        <NotificationBell />
      </div>
    </header>
  );
}
