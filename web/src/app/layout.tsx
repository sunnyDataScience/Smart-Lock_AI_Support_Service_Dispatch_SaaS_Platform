import type { Metadata } from "next";
import { Inter, Noto_Sans_TC } from "next/font/google";
import AuthGuard from "@/components/layout/AuthGuard";
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
        <AuthGuard>{children}</AuthGuard>
      </body>
    </html>
  );
}
