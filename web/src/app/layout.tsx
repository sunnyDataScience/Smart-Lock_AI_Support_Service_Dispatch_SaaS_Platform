import type { Metadata } from "next";
import { Inter, Noto_Sans_TC } from "next/font/google";
import AuthGuard from "@/components/layout/AuthGuard";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

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
  title: "SmartLock Admin",
  description: "Smart Lock AI Support & Service Dispatch Platform",
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
    >
      <body className="h-full font-primary antialiased">
        {/* WCAG 2.4.1 Bypass Blocks：第一個可 tab 元素是 skip-link，按 Enter
         * 跳到 #main-content；視覺上預設隱藏（translateY(-200%)），:focus 才滑入 */}
        <a href="#main-content" className="skip-link">
          跳到主要內容
        </a>
        {/* ToastProvider 在 body 最外層、AuthGuard 之外，登入畫面也能用 toast */}
        <ToastProvider>
          <AuthGuard>{children}</AuthGuard>
        </ToastProvider>
      </body>
    </html>
  );
}
