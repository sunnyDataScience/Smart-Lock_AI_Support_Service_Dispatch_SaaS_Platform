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

const variantStyles: Record<StatusBadgeProps["variant"], string> = {
  "in-progress": "bg-[#FEF3C7] text-[#B45309]",
  assigned: "bg-[var(--primary-light)] text-[#1D4ED8]",
  pending: "bg-[#F1F5F9] text-[#64748B]",
  completed: "bg-[#D1FAE5] text-[#065F46]",
  overdue: "bg-[#FEE2E2] text-[#DC2626]",
  urgent: "bg-[#FEF3C7] text-[#B45309]",
  normal: "bg-[#F1F5F9] text-[#64748B]",
  default: "bg-[#F1F5F9] text-[#64748B]",
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
