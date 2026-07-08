/**
 * i18n config — single source of truth for supported locales
 *
 * 為什麼自寫不裝 next-intl：
 *   admin dashboard 沒 SEO routing 需求；41 頁 zh-TW 字串已硬編，全量遷移
 *   next-intl middleware 成本過高。本實作鏡像 ThemeProvider 模式，提供
 *   useTranslations(namespace) 形狀相容 API — 未來真要換 next-intl 只需改
 *   provider 內部，components 程式碼零改動。
 *
 * 加新語系流程：
 *   1. 建 `messages/{code}.json` 鏡像 zh-TW 結構
 *   2. 在此 LOCALES 加一筆
 *   3. 完成
 */

export const LOCALES = [
  { code: "zh-TW", label: "繁體中文", nativeLabel: "繁體中文" },
  { code: "en", label: "English", nativeLabel: "English" },
] as const;

export type Locale = (typeof LOCALES)[number]["code"];

export const DEFAULT_LOCALE: Locale = "zh-TW";

export const LOCALE_STORAGE_KEY = "locale";

export function isLocale(value: unknown): value is Locale {
  return (
    typeof value === "string" &&
    LOCALES.some((l) => l.code === value)
  );
}

export function getLocaleLabel(code: Locale): string {
  return LOCALES.find((l) => l.code === code)?.label ?? code;
}
