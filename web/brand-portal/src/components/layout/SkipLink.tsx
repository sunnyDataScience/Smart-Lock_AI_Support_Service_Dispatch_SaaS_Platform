"use client";

import { useTranslations } from "@/components/i18n/LocaleProvider";

/**
 * SkipLink — WCAG 2.4.1 Bypass Blocks 跳轉連結（UAT W6-1：文字接 i18n）。
 *
 * 原本硬編碼在 server RootLayout；useTranslations 需要 LocaleProvider context，
 * 故抽成 client component、掛在 LocaleProvider 內第一個 DOM 位置（tab 順序不變）。
 */
export default function SkipLink() {
  const t = useTranslations("common");
  return (
    <a href="#main-content" className="skip-link">
      {t("skipToMain")}
    </a>
  );
}
