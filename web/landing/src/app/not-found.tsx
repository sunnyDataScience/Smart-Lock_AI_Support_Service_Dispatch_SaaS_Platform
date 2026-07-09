import Link from "next/link";
import { FileQuestion, ArrowLeft, LayoutDashboard } from "lucide-react";
import BackButton from "./_error-parts/BackButton";

/**
 * 404 — 頁面不存在
 *
 * Next.js App Router root not-found page。任何未匹配 route 或
 * 主動呼叫 `notFound()` 都會 fallback 到這裡。
 *
 * 設計原則（避免 generic AI 風格）：
 *   - 不用大型 emoji / stock illustration
 *   - 主色限制在 primary + neutrals
 *   - 大量留白，三段層次：標題 → 副標 → action
 *
 * 結構：
 *   - 本檔為 Server Component（純靜態，不需 client runtime）
 *   - "返回上一頁" 用 router.back() 必須 client，拆成 `BackButton`
 */
export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--bg-page)] px-6 py-16">
      <div className="w-full max-w-lg animate-[fadeIn_220ms_ease-out] text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--bg-surface)]">
          <FileQuestion
            className="h-7 w-7 text-[var(--text-secondary)]"
            aria-hidden="true"
          />
        </div>

        <p className="mt-6 text-[13px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          404
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-[var(--text-primary)] sm:text-[28px]">
          頁面不存在
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-[14px] leading-relaxed text-[var(--text-secondary)]">
          您訪問的頁面可能已被移除、改名，或網址輸入有誤。請確認連結後重試。
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-2 sm:flex-row sm:gap-3">
          <Link
            href="/"
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-4 py-2 text-[14px] font-medium text-[var(--text-inverse)] transition-colors hover:bg-[var(--primary-hover)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 sm:w-auto"
          >
            <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
            返回儀表板
          </Link>
          <BackButton>
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            返回上一頁
          </BackButton>
        </div>
      </div>

      {/* 純 fade-in，無反彈動畫 */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </main>
  );
}
