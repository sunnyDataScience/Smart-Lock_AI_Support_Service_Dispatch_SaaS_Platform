export interface StatusBadgeProps {
  label: string;
  variant:
    | "in-progress"
    | "assigned"
    | "pending"
    | "completed"
    | "overdue"
    | "urgent"
    | "normal"
    | "default";
}

// 統一從 globals.css 的 semantic token 讀（--badge-{tone}-bg/fg）
const variantStyles: Record<StatusBadgeProps["variant"], string> = {
  "in-progress": "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)]",
  assigned: "bg-[var(--badge-info-bg)] text-[var(--badge-info-fg)]",
  pending: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)]",
  completed: "bg-[var(--badge-success-bg)] text-[var(--badge-success-fg)]",
  overdue: "bg-[var(--badge-danger-bg)] text-[var(--badge-danger-fg)]",
  urgent: "bg-[var(--badge-warn-bg)] text-[var(--badge-warn-fg)]",
  normal: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)]",
  default: "bg-[var(--badge-muted-bg)] text-[var(--badge-muted-fg)]",
};

export default function StatusBadge({ label, variant }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-[10px] py-[3px] text-[12px] font-medium ${variantStyles[variant]}`}
    >
      {label}
    </span>
  );
}
