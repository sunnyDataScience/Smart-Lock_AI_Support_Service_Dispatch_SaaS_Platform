import type { Metadata, Viewport } from "next";
import AuthGuard from "@/components/layout/AuthGuard";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartLock 智慧派工平台",
  description: "Smart Lock AI Support & Service Dispatch Platform — Admin 後台 + 技師端 PWA",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/apple-touch-icon.svg", sizes: "180x180" }],
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Smart Lock Tech",
  },
};

export const viewport: Viewport = {
  themeColor: "#2563EB",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" className="h-full">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full font-primary antialiased">
        <AuthGuard>{children}</AuthGuard>
      </body>
    </html>
  );
}
