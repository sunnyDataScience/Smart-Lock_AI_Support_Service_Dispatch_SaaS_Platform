import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="zh-TW" className="h-full">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full font-primary antialiased">{children}</body>
    </html>
  );
}
