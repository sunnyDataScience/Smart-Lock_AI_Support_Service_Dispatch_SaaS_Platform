/**
 * Translation lookup primitives — pure functions, framework-agnostic
 *
 * Hook 形狀有意對齊 next-intl：未來真的要遷移時，只需改 `useLocale` 的後端，
 * components 用 `useTranslations("namespace")` 的呼叫不變。
 *
 * 為什麼支援 `{name}` 而非 ICU MessageFormat：
 *   admin labels 99% 不需要複數 / 性別 / 日期格式化。簡單 `{name}` 占位
 *   覆蓋既有需求；若日後需要 ICU，再換成 next-intl 是 O(provider) 重構，
 *   不是 O(callsite)。
 */

import enMessages from "@shared/i18n/messages/en.json";
import zhTWMessages from "@shared/i18n/messages/zh-TW.json";
import { DEFAULT_LOCALE, type Locale } from "@shared/i18n/config";

type Messages = Record<string, unknown>;

const MESSAGES: Record<Locale, Messages> = {
  "zh-TW": zhTWMessages as Messages,
  en: enMessages as Messages,
};

function getValue(messages: Messages | undefined, path: string): unknown {
  if (!messages) return undefined;
  return path.split(".").reduce<unknown>((acc, seg) => {
    if (acc && typeof acc === "object" && seg in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[seg];
    }
    return undefined;
  }, messages);
}

function interpolate(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const v = params[key];
    return v === undefined ? `{${key}}` : String(v);
  });
}

/**
 * Pure translate — 不在 React hook 內也能用（例如 toast helper / API error mapper）。
 *
 * 缺 key 行為：
 *   1. 先 fallback 到 DEFAULT_LOCALE
 *   2. 還缺則回傳 path 本身（比空字串好 debug — 在 UI 上會直接看到 "settings.foo.bar"）
 */
export function translate(
  locale: Locale,
  path: string,
  params?: Record<string, string | number>,
): string {
  const primary = getValue(MESSAGES[locale], path);
  const value =
    typeof primary === "string"
      ? primary
      : (getValue(MESSAGES[DEFAULT_LOCALE], path) as string | undefined);
  if (typeof value !== "string") return path;
  return interpolate(value, params);
}

export type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
) => string;

/**
 * 給 namespace 為前綴的 helper — 不依賴 React，可在任何 context 使用。
 *
 * 用例：
 *   const t = createTranslator("zh-TW", "settings.profile");
 *   t("displayName") → "顯示名稱"
 */
export function createTranslator(
  locale: Locale,
  namespace?: string,
): TranslateFn {
  return (key, params) => {
    const fullPath = namespace ? `${namespace}.${key}` : key;
    return translate(locale, fullPath, params);
  };
}
