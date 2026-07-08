"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { usePathname } from "next/navigation";

/**
 * SidebarContext — 統一管 mobile sidebar drawer 開關狀態
 *
 * 為什麼要 context：
 * - Sidebar.tsx 與 Header.tsx 在不同 React subtree
 * - Header 內的 hamburger button 要 toggle Sidebar 開關
 * - 路由切換 / Esc / 背景點擊都要關 sidebar
 * - 桌機切回行動版時 drawer 自動關 + body overflow 復原
 *
 * Provider 掛在 AuthGuard.tsx（client boundary 第一層，root layout
 * 是 server component 不能直接 wrap）。
 */

interface SidebarContextValue {
  isOpen: boolean;
  isMobile: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

const MOBILE_BREAKPOINT = "(max-width: 767.9px)"; // < md (Tailwind md = 768px)

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // 監聽斷點變化（瀏覽器 resize / 旋轉）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia(MOBILE_BREAKPOINT);
    const update = () => setIsMobile(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, []);

  // 路由切換時自動關 drawer（避免換頁殘留）
  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  // 切回桌機時關 drawer + 復原 body overflow
  useEffect(() => {
    if (!isMobile && isOpen) {
      setIsOpen(false);
    }
  }, [isMobile, isOpen]);

  // Body scroll lock when mobile drawer open
  useEffect(() => {
    if (typeof document === "undefined") return;
    const shouldLock = isMobile && isOpen;
    if (shouldLock) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [isMobile, isOpen]);

  // Esc 關 drawer
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  return (
    <SidebarContext.Provider value={{ isOpen, isMobile, open, close, toggle }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar(): SidebarContextValue {
  const ctx = useContext(SidebarContext);
  if (!ctx) {
    // Provider 未掛時的 fallback：drawer 永遠視為桌機已開（不影響桌機渲染）
    // 這允許單獨測試 Sidebar / Header 元件不需要 Provider
    return {
      isOpen: false,
      isMobile: false,
      open: () => {},
      close: () => {},
      toggle: () => {},
    };
  }
  return ctx;
}
