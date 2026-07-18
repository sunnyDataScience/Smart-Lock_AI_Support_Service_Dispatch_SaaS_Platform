import type { Metadata } from "next";
import { Inter, Noto_Sans_TC } from "next/font/google";
import AuthGuard from "@/components/layout/AuthGuard";
import { ToastProvider } from "@/components/ui/Toast";
import { ActionDialogProvider } from "@/components/ui/ActionDialog";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { LocaleProvider } from "@/components/i18n/LocaleProvider";
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
  title: "Lock AI Platform Console",
  description: "Lock AI 平台維運後台",
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
        {/* WCAG 2.4.1 Bypass Blocks：第一個可 tab 元素是 skip-link，按 Enter
         * 跳到 #main-content；視覺上預設隱藏（translateY(-200%)），:focus 才滑入 */}
        <a href="#main-content" className="skip-link">
          跳到主要內容
        </a>
        {/* Provider 嵌套順序：Theme（最外）→ Locale → Toast → AuthGuard
         *   - Theme 影響色票，最早套用避免閃白
         *   - Locale 設定 html.lang，screen reader / 字型 fallback 需要
         *   - Toast 在最內層，登入畫面也能用；t() 透過 Locale context 取得
         */}
        <ThemeProvider>
          <LocaleProvider>
            <ToastProvider>
              {/* #12:ActionDialog 取代 window.prompt/confirm,與 Toast 並存 */}
              <ActionDialogProvider>
                <AuthGuard>{children}</AuthGuard>
              </ActionDialogProvider>
            </ToastProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
