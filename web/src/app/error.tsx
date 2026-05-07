"use client";

import Link from "next/link";
import { useEffect } from "react";
import { ServerCrash, RotateCw, LayoutDashboard } from "lucide-react";

/**
 * Segment-level error boundary
 *
 * 作用：捕捉 server / client component 拋出的 runtime error，
 * 顯示友善頁面並提供 reset() 重新渲染當前 segment。
 *
 * 規範：
 *   - 必須是 Client Component（'use client'）
 *   - 接收 `{ error, reset }` props
 *   - error.digest 是 Next.js 在 server 端 hash 過的 reference id；
 *     dev 模式才會看到原始 error.message
 *
 * 留下的 console.error 是刻意的 — 等 ToastProvider 整合任務接入觀測層
 * 後再移除，不要靜默吞掉錯誤（違反 coding-style 規則）。
 */
interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: Props) {
  useEffect(() => {
    // TODO: 後續接 Sentry / OTel — 目前先進 browser console，至少留下 trace
    console.error("[error.tsx] segment error", error);
  }, [error]);

  const isDev = process.env.NODE_ENV === "development";

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-6 py-16">
      <div className="w-full max-w-lg animate-[fadeIn_220ms_ease-out]">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--bg-surface)]">
            <ServerCrash
              className="h-7 w-7 text-[var(--status-danger,#EF4444)]"
              aria-hidden="true"
            />
          </div>

          <p className="mt-6 text-[13px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            500
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-[var(--text-primary)] sm:text-[28px]">
            發生錯誤
          </h1>
          <p className="mx-auto mt-3 max-w-sm text-[14px] leading-relaxed text-[var(--text-secondary)]">
            系統暫時無法處理您的請求。請稍後再試，或聯絡技術支援團隊。
          </p>

          {error.digest && (
            <p className="mx-auto mt-4 inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-2.5 py-1 text-[12px] font-mono text-[var(--text-secondary)]">
              Reference: {error.digest}
            </p>
          )}
        </div>

        <div className="mt-8 flex flex-col items-center justify-center gap-2 sm:flex-row sm:gap-3">
          <button
            type="button"
            onClick={reset}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-4 py-2 text-[14px] font-medium text-[var(--text-inverse)] transition-colors hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 sm:w-auto"
          >
            <RotateCw className="h-4 w-4" aria-hidden="true" />
            重試
          </button>
          <Link
            href="/dashboard"
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-[14px] font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-strong,#F1F5F9)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 sm:w-auto"
          >
            <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
            返回儀表板
          </Link>
        </div>

        {isDev && (error.message || error.stack) && (
          <details
            className="mt-8 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 text-left"
            open
          >
            <summary className="cursor-pointer text-[12px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Dev: Error details
            </summary>
            {error.message && (
              <p className="mt-3 text-[13px] font-mono text-[var(--status-danger,#EF4444)]">
                {error.message}
              </p>
            )}
            {error.stack && (
              <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-[var(--surface-strong,#F1F5F9)] p-3 text-[11px] font-mono leading-relaxed text-[var(--text-secondary)]">
                {error.stack}
              </pre>
            )}
          </details>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </main>
  );
}
