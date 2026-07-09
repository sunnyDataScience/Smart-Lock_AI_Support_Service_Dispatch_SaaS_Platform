/**
 * Skeleton — 通用骨架屏
 *
 * 載入中佔位用。預設配色搭配 --bg-page，使用 CSS animate-pulse。
 * 不傳寬高時預設 fill parent。
 */

interface Props {
  className?: string;
  /** 寬度（Tailwind class 或 px） */
  width?: string;
  /** 高度（Tailwind class 或 px） */
  height?: string;
  /** 圓角樣式 */
  rounded?: "none" | "sm" | "md" | "lg" | "full";
}

const ROUNDED: Record<NonNullable<Props["rounded"]>, string> = {
  none: "rounded-none",
  sm: "rounded-sm",
  md: "rounded-md",
  lg: "rounded-lg",
  full: "rounded-full",
};

export default function Skeleton({
  className = "",
  width,
  height,
  rounded = "md",
}: Props) {
  const widthStyle = width
    ? width.includes("px") || width.includes("%")
      ? { width }
      : null
    : null;
  const heightStyle = height
    ? height.includes("px") || height.includes("%")
      ? { height }
      : null
    : null;

  const widthClass = widthStyle ? "" : width ?? "w-full";
  const heightClass = heightStyle ? "" : height ?? "h-4";

  return (
    <div
      role="presentation"
      aria-hidden="true"
      className={`animate-pulse bg-[var(--border)] ${ROUNDED[rounded]} ${widthClass} ${heightClass} ${className}`}
      style={{
        ...(widthStyle ?? {}),
        ...(heightStyle ?? {}),
      }}
    />
  );
}

/**
 * SkeletonText — 多行文字骨架（最後一行較短模擬段尾）
 */
export function SkeletonText({
  lines = 3,
  className = "",
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height="h-3"
          width={i === lines - 1 ? "w-2/3" : "w-full"}
          rounded="sm"
        />
      ))}
    </div>
  );
}

/**
 * SkeletonCard — 卡片骨架（給 KpiCard / 圖表用）
 */
export function SkeletonCard({
  height = "h-[120px]",
  className = "",
}: {
  height?: string;
  className?: string;
}) {
  return (
    <Skeleton className={`${className}`} height={height} rounded="lg" />
  );
}

/**
 * SkeletonTableRow — 表格行骨架
 */
export function SkeletonTableRow({ cols = 5 }: { cols?: number }) {
  return (
    <div className="flex items-center gap-4 px-5 py-3">
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="flex-1" height="h-3" rounded="sm" />
      ))}
    </div>
  );
}
