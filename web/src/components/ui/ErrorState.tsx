"use client";

import { AlertCircle, RotateCw } from "lucide-react";

/**
 * ErrorState — 統一錯誤狀態元件
 *
 * 取代散落各處的 `border-red-200 bg-red-50` 手刻錯誤框。
 * 三種變體：inline (flow 內) / block (大區塊) / full (整頁中央)
 */

type Variant = "inline" | "block" | "full";

interface Props {
  /** 錯誤訊息（可為字串 / Error / ApiError） */
  error: unknown;
  /** 標題文字（預設「載入失敗」） */
  title?: string;
  /** 重試 callback；提供時顯示重試按鈕 */
  onRetry?: () => void;
  /** 顯示樣式 */
  variant?: Variant;
  className?: string;
}

function describeError(e: unknown): string {
  if (e == null) return "未知錯誤";
  if (typeof e === "string") return e;
  if (typeof e === "object" && e !== null) {
    if ("errorCode" in e && "status" in e && "message" in e) {
      const err = e as { errorCode: string; status: number; message: string };
      return `${err.errorCode} (${err.status})：${err.message}`;
    }
    if ("message" in e) {
      return String((e as { message: unknown }).message);
    }
  }
  return String(e);
}

const VARIANT_STYLES: Record<Variant, string> = {
  inline:
    "rounded border border-[var(--status-danger,#FECACA)] bg-[var(--status-danger-bg,#FEF2F2)] px-3 py-2 text-[12px] text-[var(--status-danger-fg,#B91C1C)]",
  block:
    "rounded-lg border border-[var(--status-danger,#FECACA)] bg-[var(--status-danger-bg,#FEF2F2)] px-4 py-3 text-sm text-[var(--status-danger-fg,#B91C1C)]",
  full: "flex min-h-[280px] flex-col items-center justify-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-6 py-12",
};

export default function ErrorState({
  error,
  title = "載入失敗",
  onRetry,
  variant = "block",
  className = "",
}: Props) {
  const message = describeError(error);

  if (variant === "full") {
    return (
      <div className={`${VARIANT_STYLES[variant]} ${className}`} role="alert">
        <AlertCircle
          className="h-10 w-10 text-[var(--status-danger-fg,#B91C1C)]"
          aria-hidden="true"
        />
        <div className="text-base font-semibold text-[var(--text-primary)]">
          {title}
        </div>
        <div className="max-w-md text-center text-[13px] text-[var(--text-secondary)]">
          {message}
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-1.5 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--bg-page)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1"
          >
            <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />
            重試
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`${VARIANT_STYLES[variant]} ${className}`} role="alert">
      <span>
        {title}：{message}
      </span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="ml-2 inline-flex items-center gap-1 underline hover:no-underline focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1"
        >
          <RotateCw className="h-3 w-3" aria-hidden="true" />
          重試
        </button>
      )}
    </div>
  );
}
