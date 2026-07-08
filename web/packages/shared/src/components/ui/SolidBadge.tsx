export interface SolidBadgeProps {
  label: string;
  color: string;
}

export default function SolidBadge({ label, color }: SolidBadgeProps) {
  return (
    <span
      className="inline-flex h-[22px] items-center justify-center rounded-md px-2 py-[2px] text-[11px] font-semibold text-white"
      style={{ backgroundColor: color }}
    >
      {label}
    </span>
  );
}
