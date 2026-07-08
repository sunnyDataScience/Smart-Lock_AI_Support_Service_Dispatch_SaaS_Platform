"use client";

import type { RealtimeStatus } from "@shared/lib/realtime";

const STATUS_META: Record<
  RealtimeStatus,
  { label: string; color: string; pulse: boolean }
> = {
  idle: { label: "未啟用", color: "#94A3B8", pulse: false },
  disabled: { label: "未配置", color: "#94A3B8", pulse: false },
  connecting: { label: "連線中", color: "#F59E0B", pulse: true },
  open: { label: "即時連線", color: "#10B981", pulse: true },
  closed: { label: "已斷線（重試中）", color: "#94A3B8", pulse: false },
  error: { label: "連線異常（重試中）", color: "#EF4444", pulse: false },
};

interface Props {
  status: RealtimeStatus;
  labelPrefix?: string;
  compact?: boolean;
}

export default function RealtimeIndicator({
  status,
  labelPrefix,
  compact = false,
}: Props) {
  const meta = STATUS_META[status];
  if (status === "disabled" || status === "idle") {
    if (compact) return null;
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-[var(--text-secondary)]">
      <span
        className={`inline-block h-2 w-2 rounded-full ${meta.pulse ? "animate-pulse" : ""}`}
        style={{ backgroundColor: meta.color }}
        title={meta.label}
      />
      {!compact && (
        <span>
          {labelPrefix ? `${labelPrefix} ` : ""}
          {meta.label}
        </span>
      )}
    </span>
  );
}
