import { Loader2 } from "lucide-react";

/**
 * Spinner — 旋轉指示器
 *
 * 用於按鈕內、行內、區塊載入中。預設用 lucide Loader2 + Tailwind animate-spin。
 */

type Size = "xs" | "sm" | "md" | "lg";

interface Props {
  size?: Size;
  className?: string;
  /** screen reader 文字（預設「載入中…」） */
  label?: string;
}

const SIZE_MAP: Record<Size, string> = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-8 w-8",
};

export default function Spinner({
  size = "sm",
  className = "",
  label = "載入中…",
}: Props) {
  return (
    <Loader2
      role="status"
      aria-label={label}
      className={`animate-spin text-[var(--text-secondary)] ${SIZE_MAP[size]} ${className}`}
    />
  );
}
