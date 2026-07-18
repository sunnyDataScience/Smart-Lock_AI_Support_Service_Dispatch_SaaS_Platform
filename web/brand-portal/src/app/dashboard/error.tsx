"use client";

import { useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import ErrorState from "@/components/ui/ErrorState";

/**
 * /dashboard 路由 unhandled error 的全頁 fallback。
 * Next.js App Router 在 page.tsx 拋例外時自動掛載；reset() 觸發 re-render。
 */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // 之後可接 Sentry / 自家 audit log
    console.error("[dashboard] 全域錯誤：", error);
  }, [error]);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title="儀表板" subtitle="近 7 日營運概況" />
        <main className="flex flex-1 items-center justify-center px-8 py-6">
          <ErrorState
            error={error}
            title="儀表板載入失敗"
            onRetry={reset}
            variant="full"
            className="max-w-2xl"
          />
        </main>
      </div>
    </div>
  );
}
