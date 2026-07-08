"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

/**
 * BackButton — 呼叫 router.back() 的客戶端按鈕
 *
 * 拆出獨立 client subcomponent，讓 not-found.tsx 可保持為 server component。
 * 只負責歷史導航，不持有任何狀態。
 */
interface Props {
  children: ReactNode;
  className?: string;
}

export default function BackButton({ children, className = "" }: Props) {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => router.back()}
      className={`inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2 text-[14px] font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-strong,#F1F5F9)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 sm:w-auto ${className}`}
    >
      {children}
    </button>
  );
}
