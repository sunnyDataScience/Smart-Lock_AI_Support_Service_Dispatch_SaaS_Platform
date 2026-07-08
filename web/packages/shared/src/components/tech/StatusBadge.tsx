"use client";

import type { components } from "@shared/types/api.generated";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";
import { translate } from "@shared/lib/translate";
import type { Locale } from "@shared/i18n/config";

type WorkOrderStatus = components["schemas"]["WorkOrderStatus"];

// 視覺 token 與字串分離：visual map 永遠不變，label 走 i18n
const STATUS_TONE: Record<
  WorkOrderStatus,
  { bg: string; color: string }
> = {
  inquiring: { bg: "#F1F5F9", color: "#64748B" },
  qualified: { bg: "#F1F5F9", color: "#64748B" },
  quoted: { bg: "#F1F5F9", color: "#64748B" },
  negotiating: { bg: "#FEF3C7", color: "#92400E" },
  accepted: { bg: "#DBEAFE", color: "#1E40AF" },
  scheduled: { bg: "#DBEAFE", color: "#1E40AF" },
  dispatching: { bg: "#FEF3C7", color: "#92400E" },
  assigned: { bg: "#DBEAFE", color: "#1E40AF" },
  en_route: { bg: "#FED7AA", color: "#9A3412" },
  arrived: { bg: "#FED7AA", color: "#9A3412" },
  in_progress: { bg: "#FEF3C7", color: "#92400E" },
  completed: { bg: "#D1FAE5", color: "#065F46" },
  billed: { bg: "#E0E7FF", color: "#3730A3" },
  paid: { bg: "#D1FAE5", color: "#065F46" },
  closed: { bg: "#E2E8F0", color: "#475569" },
  cancelled: { bg: "#FEE2E2", color: "#991B1B" },
};

export default function StatusBadge({ status }: { status: WorkOrderStatus }) {
  const t = useTranslations("status.workOrder");
  const tone = STATUS_TONE[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-[2px] text-[11px] font-semibold"
      style={{ backgroundColor: tone.bg, color: tone.color }}
    >
      {t(status)}
    </span>
  );
}

/**
 * Locale 感知的 status label helper — 給非 React context 用（toast / template literal）。
 *
 * 在 React 內請優先用 `useTranslations("status.workOrder")(status)`，避免每次都要傳 locale。
 */
export function statusLabel(status: WorkOrderStatus, locale: Locale): string {
  return translate(locale, `status.workOrder.${status}`);
}
