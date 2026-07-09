"use client";

import { X, CheckCircle2, AlertTriangle, AlertCircle, Info } from "lucide-react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import {
  createContext,
  useCallback,
  useContext,
  useId,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

/**
 * Toast — 短暫通知元件，基於 @radix-ui/react-toast
 *
 * 提供 imperative API 給上層呼叫：
 *   const { toast } = useToast();
 *   toast({ title: "已儲存", variant: "success" });
 *
 * 視覺：左側 4px 彩條 + icon + title/description + 關閉鈕。
 * 動效：右側滑入（mobile 從上方），data-[state] 由 Radix 控制，
 * keyframes 在 globals.css。
 */

export type ToastVariant = "default" | "success" | "warning" | "error";

export interface ToastOptions {
  /** 標題（必填） */
  title: string;
  /** 副文字 */
  description?: string;
  /** 視覺變體，預設 default */
  variant?: ToastVariant;
  /** 自動關閉時間 (ms)，預設 4000，傳 Infinity 不自動關 */
  duration?: number;
}

interface ToastInstance extends ToastOptions {
  id: string;
  open: boolean;
}

interface ToastContextValue {
  toast: (opts: ToastOptions) => string;
  dismiss: (id?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

// ─────────────────────────────────────────────────────────────────────────────
// Variant 視覺對應 — 用 globals.css 變數，避免硬編色
// ─────────────────────────────────────────────────────────────────────────────

const VARIANT_BAR: Record<ToastVariant, string> = {
  default: "bg-[var(--text-secondary)]",
  success: "bg-[var(--status-success)]",
  warning: "bg-[var(--status-warning)]",
  error: "bg-[var(--status-danger)]",
};

const VARIANT_ICON_COLOR: Record<ToastVariant, string> = {
  default: "text-[var(--text-secondary)]",
  success: "text-[var(--status-success)]",
  warning: "text-[var(--status-warning)]",
  error: "text-[var(--status-danger)]",
};

function VariantIcon({ variant }: { variant: ToastVariant }) {
  const className = `h-4 w-4 ${VARIANT_ICON_COLOR[variant]}`;
  switch (variant) {
    case "success":
      return <CheckCircle2 className={className} aria-hidden="true" />;
    case "warning":
      return <AlertTriangle className={className} aria-hidden="true" />;
    case "error":
      return <AlertCircle className={className} aria-hidden="true" />;
    default:
      return <Info className={className} aria-hidden="true" />;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider — 包整個 app；管理 toast queue + 渲染 viewport
// ─────────────────────────────────────────────────────────────────────────────

export interface ToastProviderProps {
  children: ReactNode;
  /** Viewport 同時最多顯示幾個，多餘的會排隊（Radix 預設 3） */
  maxVisible?: number;
}

export function ToastProvider({ children, maxVisible = 5 }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastInstance[]>([]);
  const reactId = useId();

  const dismiss = useCallback((id?: string) => {
    setToasts((prev) => {
      if (!id) return prev.map((t) => ({ ...t, open: false }));
      return prev.map((t) => (t.id === id ? { ...t, open: false } : t));
    });
  }, []);

  // 從 state 中清除已經關閉動畫結束的 toast，避免無限堆積
  const removeFromState = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (opts: ToastOptions) => {
      const id = `${reactId}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const instance: ToastInstance = {
        ...opts,
        variant: opts.variant ?? "default",
        duration: opts.duration ?? 4000,
        id,
        open: true,
      };
      setToasts((prev) => [...prev, instance]);
      return id;
    },
    [reactId],
  );

  const ctx = useMemo<ToastContextValue>(
    () => ({ toast, dismiss }),
    [toast, dismiss],
  );

  return (
    <ToastContext.Provider value={ctx}>
      <ToastPrimitive.Provider swipeDirection="right" duration={4000}>
        {children}
        {toasts.map((t) => (
          <ToastPrimitive.Root
            key={t.id}
            open={t.open}
            duration={t.duration}
            onOpenChange={(open) => {
              if (!open) {
                // 標記為關閉，動畫結束後再從 state 移除
                setToasts((prev) =>
                  prev.map((x) => (x.id === t.id ? { ...x, open: false } : x)),
                );
                // 動畫長度約 200ms，留 50ms buffer
                setTimeout(() => removeFromState(t.id), 250);
              }
            }}
            className={[
              "ui-toast-root",
              "relative flex w-[min(360px,calc(100vw-2rem))] items-start gap-3 overflow-hidden",
              "rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]",
              "shadow-[var(--shadow-popover)]",
              "p-4 pr-10",
            ].join(" ")}
          >
            {/* 左側 4px 彩條 */}
            <span
              aria-hidden="true"
              className={`absolute left-0 top-0 h-full w-1 ${VARIANT_BAR[t.variant ?? "default"]}`}
            />
            <div className="mt-0.5 shrink-0">
              <VariantIcon variant={t.variant ?? "default"} />
            </div>
            <div className="min-w-0 flex-1">
              <ToastPrimitive.Title className="text-[14px] font-semibold leading-5 text-[var(--text-primary)]">
                {t.title}
              </ToastPrimitive.Title>
              {t.description && (
                <ToastPrimitive.Description className="mt-0.5 text-[13px] leading-5 text-[var(--text-secondary)]">
                  {t.description}
                </ToastPrimitive.Description>
              )}
            </div>
            <ToastPrimitive.Close
              aria-label="關閉"
              className="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-strong)] hover:text-[var(--text-primary)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport
          className={[
            "ui-toast-viewport",
            "fixed z-[60] flex flex-col gap-2 outline-none",
            // desktop：右上；mobile：上方滿寬
            "top-4 right-4 max-w-[calc(100vw-2rem)]",
          ].join(" ")}
          data-max-visible={maxVisible}
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook — 上層呼叫 API
// ─────────────────────────────────────────────────────────────────────────────

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used inside <ToastProvider>");
  }
  return ctx;
}
