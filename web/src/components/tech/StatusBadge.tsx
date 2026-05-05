import type { components } from "@/types/api.generated";

type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

const STATUS_META: Record<
  WorkOrderStatus,
  { label: string; bg: string; color: string }
> = {
  inquiring: { label: "詢問中", bg: "#F1F5F9", color: "#64748B" },
  qualified: { label: "已審核", bg: "#F1F5F9", color: "#64748B" },
  quoted: { label: "已報價", bg: "#F1F5F9", color: "#64748B" },
  negotiating: { label: "議價中", bg: "#FEF3C7", color: "#92400E" },
  accepted: { label: "已接單", bg: "#DBEAFE", color: "#1E40AF" },
  scheduled: { label: "已排程", bg: "#DBEAFE", color: "#1E40AF" },
  dispatching: { label: "派工中", bg: "#FEF3C7", color: "#92400E" },
  assigned: { label: "已指派", bg: "#DBEAFE", color: "#1E40AF" },
  en_route: { label: "前往中", bg: "#FED7AA", color: "#9A3412" },
  arrived: { label: "已抵達", bg: "#FED7AA", color: "#9A3412" },
  in_progress: { label: "作業中", bg: "#FEF3C7", color: "#92400E" },
  completed: { label: "已完工", bg: "#D1FAE5", color: "#065F46" },
  billed: { label: "已開單", bg: "#E0E7FF", color: "#3730A3" },
  paid: { label: "已付款", bg: "#D1FAE5", color: "#065F46" },
  closed: { label: "已結案", bg: "#E2E8F0", color: "#475569" },
  cancelled: { label: "已取消", bg: "#FEE2E2", color: "#991B1B" },
};

export default function StatusBadge({ status }: { status: WorkOrderStatus }) {
  const meta = STATUS_META[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-[2px] text-[11px] font-semibold"
      style={{ backgroundColor: meta.bg, color: meta.color }}
    >
      {meta.label}
    </span>
  );
}

export function statusLabel(status: WorkOrderStatus): string {
  return STATUS_META[status].label;
}
