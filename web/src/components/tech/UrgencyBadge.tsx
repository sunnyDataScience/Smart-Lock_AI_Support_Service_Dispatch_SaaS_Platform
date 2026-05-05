import type { components } from "@/types/api.generated";

type Urgency = components["schemas"]["Urgency"];

const URGENCY_META: Record<
  Urgency,
  { label: string; bg: string; color: string; pulse?: boolean } | null
> = {
  low: null,
  medium: { label: "急件", bg: "#F59E0B", color: "#FFFFFF" },
  high: { label: "Red Code", bg: "#EF4444", color: "#FFFFFF", pulse: true },
};

export default function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  const meta = URGENCY_META[urgency];
  if (!meta) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-[2px] text-[11px] font-bold ${
        meta.pulse ? "animate-pulse" : ""
      }`}
      style={{ backgroundColor: meta.bg, color: meta.color }}
    >
      {meta.label}
    </span>
  );
}
