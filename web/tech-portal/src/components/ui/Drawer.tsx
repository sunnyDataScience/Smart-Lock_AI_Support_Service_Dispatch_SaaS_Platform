"use client";

import { X } from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { forwardRef } from "react";
import type { ComponentPropsWithoutRef, ElementRef, ReactNode } from "react";

/**
 * Drawer — 側邊面板元件，基於 @radix-ui/react-dialog
 *
 * 與 Modal 共用 Radix Dialog primitive，但定位為從邊緣滑入的 side panel。
 * 支援 right（預設）/ left / bottom 三向；mobile-first 場景常用 bottom。
 *
 * focus trap、ESC、aria-* 由 Radix 提供，不自寫鍵盤處理或拖拉手勢。
 *
 * 動效實作放在 globals.css 的 .ui-drawer-content-{side}，
 * 透過 Radix data-[state] 切換 transform。
 *
 * 用法：
 *   <Drawer open={open} onOpenChange={setOpen}>
 *     <DrawerContent side="right" size="md">
 *       <DrawerHeader>
 *         <DrawerTitle>詳情</DrawerTitle>
 *       </DrawerHeader>
 *       <div className="px-6 py-4">主體</div>
 *     </DrawerContent>
 *   </Drawer>
 */

export type DrawerSide = "right" | "left" | "bottom";
export type DrawerSize = "sm" | "md" | "lg";

const SIDE_BASE: Record<DrawerSide, string> = {
  right: "fixed right-0 top-0 bottom-0 h-full",
  left: "fixed left-0 top-0 bottom-0 h-full",
  bottom: "fixed inset-x-0 bottom-0",
};

// 寬度對應（right / left）
const HORIZONTAL_SIZE: Record<DrawerSize, string> = {
  sm: "w-80",
  md: "w-96",
  lg: "w-[28rem]",
};

// 高度對應（bottom）— 採用 mobile-first 邏輯，最小高度確保內容可讀
const BOTTOM_SIZE: Record<DrawerSize, string> = {
  sm: "max-h-[40vh]",
  md: "max-h-[60vh]",
  lg: "max-h-[80vh]",
};

const SIDE_ANIM_CLASS: Record<DrawerSide, string> = {
  right: "ui-drawer-content-right",
  left: "ui-drawer-content-left",
  bottom: "ui-drawer-content-bottom",
};

// Root — re-export Radix primitives
export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;
export const DrawerPortal = DialogPrimitive.Portal;
export const DrawerClose = DialogPrimitive.Close;

// ─────────────────────────────────────────────────────────────────────────────
// Overlay
// ─────────────────────────────────────────────────────────────────────────────

export type DrawerOverlayProps = ComponentPropsWithoutRef<
  typeof DialogPrimitive.Overlay
>;

export const DrawerOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  DrawerOverlayProps
>(function DrawerOverlay({ className = "", ...rest }, ref) {
  return (
    <DialogPrimitive.Overlay
      ref={ref}
      className={`ui-modal-overlay fixed inset-0 z-50 bg-black/40 ${className}`}
      {...rest}
    />
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Content
// ─────────────────────────────────────────────────────────────────────────────

export interface DrawerContentProps
  extends ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  /** 滑入方向，預設 right */
  side?: DrawerSide;
  /** 大小，預設 md（水平方向控制寬度，bottom 控制最大高度） */
  size?: DrawerSize;
  /** 是否顯示右上角 X 關閉鈕，預設 true */
  showCloseButton?: boolean;
  /** 自訂 overlay className */
  overlayClassName?: string;
}

export const DrawerContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  DrawerContentProps
>(function DrawerContent(
  {
    side = "right",
    size = "md",
    showCloseButton = true,
    className = "",
    overlayClassName,
    children,
    ...rest
  },
  ref,
) {
  const sizeClass =
    side === "bottom" ? BOTTOM_SIZE[size] : HORIZONTAL_SIZE[size];

  // bottom drawer 圓角只放上方；side drawer 不加圓角（貼齊邊）
  const radiusClass =
    side === "bottom" ? "rounded-t-lg" : "";

  // 邊框：side drawer 對著螢幕內側畫線，bottom drawer 只畫頂線
  const borderClass =
    side === "right"
      ? "border-l border-[var(--border)]"
      : side === "left"
      ? "border-r border-[var(--border)]"
      : "border-t border-[var(--border)]";

  return (
    <DrawerPortal>
      <DrawerOverlay className={overlayClassName} />
      <DialogPrimitive.Content
        ref={ref}
        className={[
          SIDE_ANIM_CLASS[side],
          SIDE_BASE[side],
          sizeClass,
          radiusClass,
          borderClass,
          "z-50 flex flex-col",
          "bg-[var(--bg-surface)] text-[var(--text-primary)]",
          "shadow-[var(--shadow-popover)]",
          // bottom drawer 在小螢幕全寬，水平方向最大寬度避免 desktop 上太寬
          side === "bottom" ? "" : "max-w-[100vw]",
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
    </DrawerPortal>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Layout helpers
// ─────────────────────────────────────────────────────────────────────────────

export interface DrawerHeaderProps {
  children: ReactNode;
  className?: string;
}

export function DrawerHeader({ children, className = "" }: DrawerHeaderProps) {
  return (
    <div
      className={`flex flex-col gap-1 border-b border-[var(--border)] px-6 py-4 pr-12 ${className}`}
    >
      {children}
    </div>
  );
}

export type DrawerTitleProps = ComponentPropsWithoutRef<
  typeof DialogPrimitive.Title
>;

export const DrawerTitle = forwardRef<
  ElementRef<typeof DialogPrimitive.Title>,
  DrawerTitleProps
>(function DrawerTitle({ className = "", ...rest }, ref) {
  return (
    <DialogPrimitive.Title
      ref={ref}
      className={`text-base font-semibold text-[var(--text-primary)] ${className}`}
      {...rest}
    />
  );
});

export type DrawerDescriptionProps = ComponentPropsWithoutRef<
  typeof DialogPrimitive.Description
>;

export const DrawerDescription = forwardRef<
  ElementRef<typeof DialogPrimitive.Description>,
  DrawerDescriptionProps
>(function DrawerDescription({ className = "", ...rest }, ref) {
  return (
    <DialogPrimitive.Description
      ref={ref}
      className={`text-[13px] text-[var(--text-secondary)] ${className}`}
      {...rest}
    />
  );
});

export interface DrawerFooterProps {
  children: ReactNode;
  className?: string;
}

export function DrawerFooter({ children, className = "" }: DrawerFooterProps) {
  return (
    <div
      className={`mt-auto flex items-center justify-end gap-2 border-t border-[var(--border)] px-6 py-3 ${className}`}
    >
      {children}
    </div>
  );
}
