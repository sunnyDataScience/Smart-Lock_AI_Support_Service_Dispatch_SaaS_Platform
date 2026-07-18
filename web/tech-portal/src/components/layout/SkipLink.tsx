"use client";

import { useTranslations } from "@/components/i18n/LocaleProvider";

/**
 * SkipLink — WCAG 2.4.1 Bypass Blocks 跳到主要內容連結。
 *
 * UAT W6-6：原本硬編碼在 root layout（server component）內，英文模式仍顯示中文。
 * 抽成 client component 走 i18n；SSR 首屏用預設語系（zh-TW），client mount 後
 * 由 LocaleProvider 校正 —— 與全站其他文案的行為一致，無 hydration mismatch。
 * 必須維持為 body 內第一個可 tab 元素（放在 LocaleProvider 內最前面）。
 */
export default function SkipLink() {
  const t = useTranslations("a11y");
  return (
    <a href="#main-content" className="skip-link">
      {t("skipToMain")}
    </a>
  );
}
