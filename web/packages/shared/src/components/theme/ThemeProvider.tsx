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

/**
 * ThemeProvider — 全站深色模式 context
 *
 * 三選：
 *   - "system"：跟隨 OS 的 prefers-color-scheme
 *   - "light" ：強制淺色
 *   - "dark"  ：強制深色
 *
 * 持久化：localStorage("theme")，預設 "system"。
 *
 * 為什麼配合 layout.tsx 的 inline script：
 *   React 載入前如果不先 setAttribute("data-theme")，會閃白一下。
 *   inline script 在 <head> 同步執行（blocking），保證第一帧就是正確顏色。
 *   ThemeProvider 載入後接手，但邏輯需與 inline script 完全一致才不會回跳。
 *
 * 為什麼 setTheme("system") 後 resolvedTheme 會自動更新：
 *   useEffect 監聽 prefers-color-scheme change，OS 切換時自動 re-apply。
 */

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

const STORAGE_KEY = "theme";
const DEFAULT_THEME: Theme = "system";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw === "light" || raw === "dark" || raw === "system") return raw;
  return DEFAULT_THEME;
}

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme === "system") {
    if (typeof window === "undefined") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return theme;
}

function applyThemeAttribute(resolved: ResolvedTheme) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", resolved);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // SSR 安全：初始用 DEFAULT，client mount 後再校正
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("light");

  // mount 時讀 localStorage（避免 hydration mismatch 直接讀 window）
  useEffect(() => {
    const stored = readStoredTheme();
    setThemeState(stored);
  }, []);

  // theme 變動 → 計算 resolved + 套用 attribute + 監聽 OS 變動
  useEffect(() => {
    const apply = () => {
      const resolved = resolveTheme(theme);
      applyThemeAttribute(resolved);
      setResolvedTheme(resolved);
    };
    apply();

    // system 模式才需要監聽 OS 變動；強制 light/dark 不需要
    if (theme !== "system") return;
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    mql.addEventListener("change", apply);
    return () => {
      mql.removeEventListener("change", apply);
    };
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
    setThemeState(next);
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside <ThemeProvider>");
  }
  return ctx;
}
