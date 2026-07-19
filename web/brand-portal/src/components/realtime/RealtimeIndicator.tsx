"use client";

import type { RealtimeStatus } from "@/lib/realtime";
import { useTranslations } from "@/components/i18n/LocaleProvider";

// Tone（顏色 / pulse）與 label（i18n）分離 —— label 由 components.realtimeIndicator.* 解析
const STATUS_TONE: Record<RealtimeStatus, { color: string; pulse: boolean }> = {
  idle: { color: "#94A3B8", pulse: false },
  disabled: { color: "#94A3B8", pulse: false },
  connecting: { color: "#F59E0B", pulse: true },
  open: { color: "#10B981", pulse: true },
  closed: { color: "#94A3B8", pulse: false },
  error: { color: "#EF4444", pulse: false },
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
  const t = useTranslations("components.realtimeIndicator");
  const tone = STATUS_TONE[status];
  const label = t(status);
  if (status === "disabled" || status === "idle") {
    if (compact) return null;
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-[var(--text-secondary)]">
      <span
        className={`inline-block h-2 w-2 rounded-full ${tone.pulse ? "animate-pulse" : ""}`}
        style={{ backgroundColor: tone.color }}
        title={label}
      />
      {!compact && (
        <span>
          {labelPrefix ? `${labelPrefix} ` : ""}
          {label}
        </span>
      )}
    </span>
  );
}
