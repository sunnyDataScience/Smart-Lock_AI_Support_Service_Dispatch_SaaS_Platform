"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  isLocale,
  type Locale,
} from "@shared/i18n/config";
import { createTranslator, type TranslateFn } from "@shared/lib/translate";

/**
 * LocaleProvider — 全站語系 context
 *
 * 鏡像 ThemeProvider 的形狀：
 *   - localStorage("locale") 持久化，預設 zh-TW
 *   - mount 後 useEffect 讀取 → 同步 React state + html.lang attribute
 *   - SSR 安全（首屏走預設值，client mount 後校正）
 *
 * 為什麼不做 inline FOUC script（與 theme 不同）：
 *   theme 切換影響顏色，閃白會被注意到（RGB 視覺差大）。
 *   locale 切換影響文字，使用者看到 zh-TW 字 ~50ms 才換 en，認知上是「載入完成」
 *   而非「閃爍」。admin tool 只在登入後使用，不是公開內容，所以不投資 SSR-aware
 *   解法。如果未來要做訪客端公開頁（如 `/track/[token]`），可以個別頁面加 SSR
 *   locale 解析。
 *
 * 為什麼動態更新 html.lang：
 *   螢幕閱讀器、瀏覽器拼字檢查、CJK 字型 fallback 都會看 `<html lang>`。
 *   靜態寫死 lang="zh-TW" 在 en 模式下會讓 SR 用中文發音念英文。
 */

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: TranslateFn;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return isLocale(raw) ? raw : DEFAULT_LOCALE;
}

function applyHtmlLang(locale: Locale) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("lang", locale);
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  // SSR 安全：首屏用 DEFAULT，client mount 後校正
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = readStoredLocale();
    setLocaleState(stored);
    applyHtmlLang(stored);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    }
    applyHtmlLang(next);
    setLocaleState(next);
  }, []);

  // top-level t（不指定 namespace）— 提供無 namespace 的 callsite
  const t = useMemo<TranslateFn>(
    () => createTranslator(locale),
    [locale],
  );

  const value = useMemo<LocaleContextValue>(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocale must be used inside <LocaleProvider>");
  }
  return ctx;
}

/**
 * 與 next-intl 形狀一致的翻譯 hook。
 *
 * 用例：
 *   const t = useTranslations("settings.profile");
 *   <span>{t("displayName")}</span>           // → "顯示名稱"
 *   <span>{t("greeting", { name: "Alice" })}</span>  // → "Hello Alice"（如果 en）
 */
export function useTranslations(namespace?: string): TranslateFn {
  const { locale } = useLocale();
  return useMemo(
    () => createTranslator(locale, namespace),
    [locale, namespace],
  );
}
