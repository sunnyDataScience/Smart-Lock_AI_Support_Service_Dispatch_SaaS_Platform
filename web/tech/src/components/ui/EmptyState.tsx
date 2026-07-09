import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

/**
 * EmptyState — 空資料狀態
 *
 * 用於列表 / 表格 / 卡片無資料時的提示。
 */

interface Props {
  /** 圖示，預設 Inbox */
  icon?: LucideIcon;
  /** 標題（粗體） */
  title?: string;
  /** 描述文字（淺色） */
  description?: string;
  /** 操作按鈕（如「新建」按鈕） */
  action?: React.ReactNode;
  /** 高度（預設 240px，inline 變體可改 120px） */
  height?: string;
  className?: string;
}

export default function EmptyState({
  icon: Icon = Inbox,
  title = "目前無資料",
  description,
  action,
  height = "h-[240px]",
  className = "",
}: Props) {
  return (
    <div
      className={`flex ${height} flex-col items-center justify-center gap-2 px-6 ${className}`}
    >
      <Icon
        className="h-8 w-8 text-[var(--text-disabled,#A1A1AA)]"
        aria-hidden="true"
      />
      <div className="text-[14px] font-medium text-[var(--text-primary)]">
        {title}
      </div>
      {description && (
        <div className="max-w-sm text-center text-[12px] text-[var(--text-secondary)]">
          {description}
        </div>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
