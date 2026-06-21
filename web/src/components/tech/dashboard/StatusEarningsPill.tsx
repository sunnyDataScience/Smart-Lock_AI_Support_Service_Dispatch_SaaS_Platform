"use client";

import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Availability = components["schemas"]["Technician"]["availability"];

const DOT_COLOR: Record<Availability, string> = {
  available: "#10B981",
  busy: "#F59E0B",
  offline: "#94A3B8",
  on_leave: "#94A3B8",
  circuit_breaker_open: "#EF4444",
};

interface Props {
  availability: Availability;
  /** 顯示金額（已格式化字串，如 "NT$ 12,400"）；無資料傳 null。 */
  amountLabel: string | null;
  /** 金額的口徑說明（如「本月已結淨額」）。 */
  caption: string;
}

/**
 * StatusEarningsPill — 決策屏頂部狀態/收入膠囊（DoorDash earnings pill）。
 * 左：上線狀態指示燈 + 文字；右：收入金額 + 口徑。
 */
export default function StatusEarningsPill({ availability, amountLabel, caption }: Props) {
  const t = useTranslations("techPortal.home.status");

  return (
    <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: DOT_COLOR[availability] }}
        />
        <span className="text-[14px] font-semibold text-[var(--text-primary)]">
          {t(availability)}
        </span>
      </div>
      <div className="flex flex-col items-end">
        <span className="text-[16px] font-bold text-[#059669]">
          {amountLabel ?? "—"}
        </span>
        <span className="text-[11px] text-[var(--text-disabled)]">{caption}</span>
      </div>
    </div>
  );
}
