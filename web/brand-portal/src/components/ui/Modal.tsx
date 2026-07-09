"use client";

import { X } from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { forwardRef } from "react";
import type { ComponentPropsWithoutRef, ElementRef, ReactNode } from "react";

/**
 * Modal — 統一對話框元件，基於 @radix-ui/react-dialog
 *
 * 提供 focus trap、ESC 關閉、aria-labelledby/describedby（Radix 自動處理），
 * 動效用 fade-in + scale-up（150ms ease-out），與 ErrorState/EmptyState
 * 風格保持一致（rounded-lg、shadow-popover、border-[var(--border)]）。
 *
 * 動效實作放在 globals.css 的 .ui-modal-overlay / .ui-modal-content，
 * 透過 Radix data-[state] attribute 切換，不依賴 tailwindcss-animate plugin。
 *
 * 用法：
 *   <Modal open={isOpen} onOpenChange={setOpen}>
 *     <ModalContent size="md">
 *       <ModalHeader>
 *         <ModalTitle>標題</ModalTitle>
 *         <ModalDescription>說明文字</ModalDescription>
 *       </ModalHeader>
 *       <div className="px-6 py-4">主體內容</div>
 *       <ModalFooter>
 *         <ModalClose>取消</ModalClose>
 *       </ModalFooter>
 *     </ModalContent>
 *   </Modal>
 */

export type ModalSize = "sm" | "md" | "lg" | "xl";

const SIZE_MAP: Record<ModalSize, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

// Root wrapper — 直接 re-export Radix Root，保留其 controlled/uncontrolled API
export const Modal = DialogPrimitive.Root;

export const ModalTrigger = DialogPrimitive.Trigger;

export const ModalPortal = DialogPrimitive.Portal;

// ─────────────────────────────────────────────────────────────────────────────
// Overlay — 半透明背景 + 微量 backdrop blur
// ─────────────────────────────────────────────────────────────────────────────

export type ModalOverlayProps = ComponentPropsWithoutRef<
  typeof DialogPrimitive.Overlay
>;

export const ModalOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  ModalOverlayProps
>(function ModalOverlay({ className = "", ...rest }, ref) {
  return (
    <DialogPrimitive.Overlay
      ref={ref}
      className={`ui-modal-overlay fixed inset-0 z-50 bg-black/40 ${className}`}
      {...rest}
    />
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Content — 居中、圓角、shadow，含右上 X 關閉按鈕
// ─────────────────────────────────────────────────────────────────────────────

export interface ModalContentProps
  extends ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  /** 對話框寬度，預設 md */
  size?: ModalSize;
  /** 是否顯示右上角 X 關閉鈕，預設 true */
  showCloseButton?: boolean;
  /** 自訂 overlay className（少用） */
  overlayClassName?: string;
}

export const ModalContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  ModalContentProps
>(function ModalContent(
  {
    size = "md",
    showCloseButton = true,
    className = "",
    overlayClassName,
    children,
    ...rest
  },
  ref,
) {
  return (
    <ModalPortal>
      <ModalOverlay className={overlayClassName} />
      <DialogPrimitive.Content
        ref={ref}
        className={[
          "ui-modal-content",
          "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)]",
          SIZE_MAP[size],
          "-translate-x-1/2 -translate-y-1/2",
          "rounded-lg border border-[var(--border)]",
          "bg-[var(--bg-surface)] text-[var(--text-primary)]",
          "shadow-[var(--shadow-popover)]",
          "max-h-[calc(100vh-4rem)] overflow-y-auto",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...rest}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            aria-label="關閉"
            className="absolute right-4 top-4 inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-strong)] hover:text-[var(--text-primary)] focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-1"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </ModalPortal>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Layout helpers
// ─────────────────────────────────────────────────────────────────────────────

export interface ModalHeaderProps {
  children: ReactNode;
  className?: string;
}

export function ModalHeader({ children, className = "" }: ModalHeaderProps) {
  return (
    <div
      className={`flex flex-col gap-1 border-b border-[var(--border)] px-6 py-4 pr-12 ${className}`}
    >
      {children}
    </div>
  );
}

export type ModalTitleProps = ComponentPropsWithoutRef<
  typeof DialogPrimitive.Title
>;

export const ModalTitle = forwardRef<
  ElementRef<typeof DialogPrimitive.Title>,
  ModalTitleProps
>(function ModalTitle({ className = "", ...rest }, ref) {
  return (
    <DialogPrimitive.Title
      ref={ref}
      className={`text-base font-semibold text-[var(--text-primary)] ${className}`}
      {...rest}
    />
  );
});

export type ModalDescriptionProps = ComponentPropsWithoutRef<
  typeof DialogPrimitive.Description
>;

export const ModalDescription = forwardRef<
  ElementRef<typeof DialogPrimitive.Description>,
  ModalDescriptionProps
>(function ModalDescription({ className = "", ...rest }, ref) {
  return (
    <DialogPrimitive.Description
      ref={ref}
      className={`text-[13px] text-[var(--text-secondary)] ${className}`}
      {...rest}
    />
  );
});

export interface ModalFooterProps {
  children: ReactNode;
  className?: string;
}

export function ModalFooter({ children, className = "" }: ModalFooterProps) {
  return (
    <div
      className={`flex items-center justify-end gap-2 border-t border-[var(--border)] px-6 py-3 ${className}`}
    >
      {children}
    </div>
  );
}

export const ModalClose = DialogPrimitive.Close;
