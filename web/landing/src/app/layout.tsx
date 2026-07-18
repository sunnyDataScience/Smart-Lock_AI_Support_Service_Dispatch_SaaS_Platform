import type { Metadata } from "next";
import { Inter, Noto_Sans_TC } from "next/font/google";
import AuthGuard from "@/components/layout/AuthGuard";
import { ToastProvider } from "@/components/ui/Toast";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { LocaleProvider } from "@/components/i18n/LocaleProvider";
import LocaleChrome from "@/components/i18n/LocaleChrome";
import "./globals.css";

/**
 * FOUC 防閃白 inline script — 在 React hydration 前同步執行
 *
 * 為什麼必須 inline 在 <head>：
 *   ThemeProvider 是 client component，要等 React 載入完才能讀 localStorage
 *   並 setAttribute。中間這一段時間瀏覽器會用 :root 的 light 變數渲染，
 *   user 在深色模式下會看到一閃的白屏。
 *
 * 為什麼用 IIFE + setAttribute 而不用 className：
 *   CSS 是用 [data-theme="dark"] 選擇器，跟 ThemeProvider 內部邏輯一致。
 *   完全不依賴 React，純 DOM 操作，最快路徑。
 *
 * 注意：本 script 必須與 ThemeProvider 的 resolveTheme() 邏輯完全一致，
 *       否則 hydration 後會跳一下顏色。
 */
const themeFOUCScript = `(function(){try{var k='theme';var t=localStorage.getItem(k);if(t!=='light'&&t!=='dark'&&t!=='system')t='system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.setAttribute('data-theme',d?'dark':'light');}catch(e){}})();`;

// next/font 在 build time 自托管 Google Fonts，避免 runtime FOIT/CLS
// 並節省一次 fonts.googleapis.com round-trip
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

const notoSansTC = Noto_Sans_TC({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-noto-sans-tc",
  display: "swap",
});

export const metadata: Metadata = {
  // 品牌名對齊頁面內文案「SmartLock」(UAT:分頁 title 曾誤植 LockSmart)
  title: "SmartLock 智慧鎖服務",
  description: "智慧鎖 AI 客服與到府維修服務",
  icons: {
    icon: "/favicon.png",
    apple: "/icons/apple-touch-icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="zh-TW"
      className={`h-full ${inter.variable} ${notoSansTC.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* 必須在 React hydration 前先 set data-theme 防閃白；suppressHydrationWarning
         * 加在 <html> 上是因為 inline script 會修改 attribute，避免 React 警告。 */}
        <script dangerouslySetInnerHTML={{ __html: themeFOUCScript }} />
      </head>
      <body className="h-full font-primary antialiased">
        {/* Provider 嵌套順序：Theme（最外）→ Locale → Toast → AuthGuard
         *   - Theme 影響色票，最早套用避免閃白
         *   - Locale 設定 html.lang，screen reader / 字型 fallback 需要
         *   - Toast 在最內層，登入畫面也能用；t() 透過 Locale context 取得
         * WCAG 2.4.1 Bypass Blocks：skip-link 在 LocaleChrome 內、為 DOM 第一個
         * 可 tab 元素（Provider 本身不產生 DOM）；UAT W6-6 改由 client 依語系渲染，
         * 並同步 document.title。
         */}
        <ThemeProvider>
          <LocaleProvider>
            <LocaleChrome />
            <ToastProvider>
              <AuthGuard>{children}</AuthGuard>
            </ToastProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
