"use client";

import { useMemo } from "react";
import { Star, Ellipsis } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type Availability = Technician["availability"];

interface Props {
  items: Technician[];
  loading?: boolean;
  /** 核准 pending_approval 技師（onboarding → active）。 */
  onApprove?: (tech: Technician) => void;
  /** 正在核准中的技師 id（按鈕轉 loading + disabled）。 */
  approvingId?: string | null;
}

// onboarding 生命週期狀態徽章顏色（label 由 i18n）
// 合法值集合對齊 SQL/migrations/020-tech-lifecycle.sql + technician_lifecycle_service
// （pending_approval / active / inactive / suspended / rejected / terminated）。
// inactive 為非懲罰性「停用」（可重新啟用回 active，異於懲罰性 suspended 停權）→ 中性灰調。
const ONBOARD_TONE: Record<string, { textColor: string; bgColor: string }> = {
  pending_approval: { textColor: "#92400E", bgColor: "#FEF3C7" },
  active: { textColor: "#065F46", bgColor: "#D1FAE5" },
  inactive: { textColor: "#475569", bgColor: "#F1F5F9" },
  suspended: { textColor: "#92400E", bgColor: "#FEF3C7" },
  terminated: { textColor: "#991B1B", bgColor: "#FEE2E2" },
  rejected: { textColor: "#991B1B", bgColor: "#FEE2E2" },
};

// Tone（顏色）— label 由 i18n 提供
const AVAILABILITY_TONE: Record<
  Availability,
  { textColor: string; bgColor: string }
> = {
  available: { textColor: "#065F46", bgColor: "#D1FAE5" },
  busy: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
  offline: { textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" },
  on_leave: { textColor: "#92400E", bgColor: "#FEF3C7" },
  circuit_breaker_open: { textColor: "#991B1B", bgColor: "#FEE2E2" },
};

const BRAND_STYLE: Record<string, { textColor: string; bgColor: string }> = {
  Yale: { textColor: "#92400E", bgColor: "#FEF3C7" },
  Chatlock: { textColor: "#3730A3", bgColor: "#E0E7FF" },
  美樂: { textColor: "#065F46", bgColor: "#D1FAE5" },
  "Mi-La": { textColor: "#065F46", bgColor: "#D1FAE5" },
  Dormakaba: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
};

const FALLBACK_BRAND = { textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" };

const AVATAR_PALETTE = ["#DBEAFE", "#FEF3C7", "#FCE7F3", "#E0E7FF", "#D1FAE5", "#FEE2E2", "#F3E8FF", "#FFEDD5"];

function avatarColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length];
}

export default function TechniciansTable({ items, loading, onApprove, approvingId }: Props) {
  const t = useTranslations("components.technicians.table");

  // onboarding 狀態 label（i18n；缺則回退原值）
  const onboardLabel = (status: string | null | undefined): string =>
    status ? t(`onboardStatus.${status}`) : "";

  const columns = useMemo(
    () => [
      { label: "", width: "w-[52px] shrink-0" },
      { label: t("cols.technician"), width: "w-[200px] shrink-0" },
      { label: t("cols.brands"), width: "w-[180px] shrink-0" },
      { label: t("cols.region"), width: "w-[180px] shrink-0" },
      { label: t("cols.rating"), width: "w-[80px] shrink-0" },
      { label: t("cols.status"), width: "w-[100px] shrink-0" },
      { label: t("cols.completed"), width: "w-[100px] shrink-0" },
      { label: t("cols.actions"), width: "flex-1 min-w-0" },
    ],
    [t],
  );

  const availabilityLabels: Record<Availability, string> = useMemo(
    () => ({
      available: t("availability.available"),
      busy: t("availability.busy"),
      offline: t("availability.offline"),
      on_leave: t("availability.on_leave"),
      circuit_breaker_open: t("availability.circuit_breaker_open"),
    }),
    [t],
  );

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-[var(--bg-surface)]">
      {/* Header Row */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-8">
        <div className="flex w-[52px] shrink-0 items-center">
          <div className="h-[18px] w-[18px] rounded border-[1.5px] border-[var(--border)]" />
        </div>
        {columns.slice(1).map((col) => (
          <div key={col.label} className={`flex items-center ${col.width}`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Body */}
      {loading && items.length === 0 ? (
        <div className="flex min-w-0 flex-1 items-center justify-center py-12 text-sm text-[var(--text-secondary)]">
          {t("loading")}
        </div>
      ) : items.length === 0 ? (
        <div className="flex min-w-0 flex-1 items-center justify-center py-12 text-sm text-[var(--text-secondary)]">
          {t("empty")}
        </div>
      ) : (
        items.map((tech) => {
          const tone = AVAILABILITY_TONE[tech.availability] ?? AVAILABILITY_TONE.available;
          const availabilityLabel =
            availabilityLabels[tech.availability] ?? availabilityLabels.available;
          const brands = (tech.skills ?? []).slice(0, 3);
          const region = (tech.service_areas ?? []).slice(0, 2).join("、") || "—";
          return (
            <div
              key={tech.id}
              className="flex h-[60px] items-center border-b border-[var(--border)] px-8"
            >
              {/* Checkbox */}
              <div className="flex w-[52px] shrink-0 items-center">
                <div className="h-[18px] w-[18px] rounded border-[1.5px] border-[var(--border)]" />
              </div>

              {/* Tech info */}
              <div className="flex w-[200px] shrink-0 items-center gap-[10px]">
                <div
                  className="h-9 w-9 flex-shrink-0 rounded-full"
                  style={{ backgroundColor: avatarColor(tech.id) }}
                />
                <div className="flex flex-col gap-[2px]">
                  <Link
                    href={`/technicians/${tech.id}`}
                    className="text-[14px] font-medium text-[var(--text-primary)] hover:underline"
                  >
                    {tech.name}
                  </Link>
                  <span className="font-['IBM_Plex_Mono'] text-[11px] text-[var(--text-secondary)]">
                    {tech.phone}
                  </span>
                </div>
              </div>

              {/* Brands */}
              <div className="flex w-[180px] shrink-0 flex-wrap items-center gap-1">
                {brands.length > 0 ? (
                  brands.map((b) => {
                    const style = BRAND_STYLE[b] ?? FALLBACK_BRAND;
                    return (
                      <span
                        key={b}
                        className="rounded px-2 py-[2px] text-[11px] font-medium"
                        style={{ color: style.textColor, backgroundColor: style.bgColor }}
                      >
                        {b}
                      </span>
                    );
                  })
                ) : (
                  <span className="text-[11px] text-[var(--text-disabled)]">—</span>
                )}
              </div>

              {/* Region */}
              <div className="flex w-[180px] shrink-0 items-center">
                <span className="text-[13px] text-[var(--text-primary)]">
                  {region}
                </span>
              </div>

              {/* Rating */}
              <div className="flex w-[80px] shrink-0 items-center gap-1">
                <Star className="h-[14px] w-[14px] fill-[var(--accent)] text-[var(--accent)]" />
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                  {tech.rating.toFixed(1)}
                </span>
              </div>

              {/* Status */}
              <div className="flex w-[100px] shrink-0 items-center">
                <span
                  className="rounded-full px-[10px] py-[3px] text-[12px] font-medium"
                  style={{ color: tone.textColor, backgroundColor: tone.bgColor }}
                >
                  {availabilityLabel}
                </span>
              </div>

              {/* Completed Orders */}
              <div className="flex w-[100px] shrink-0 items-center">
                <span className="text-[14px] font-semibold text-[var(--primary)]">
                  {tech.completed_orders_count ?? 0}
                </span>
              </div>

              {/* Actions — pending_approval 顯核准鈕；其他非 active 顯 onboarding 狀態徽章 */}
              <div className="flex min-w-0 flex-1 items-center gap-2">
                {tech.status === "pending_approval" ? (
                  <button
                    type="button"
                    onClick={() => onApprove?.(tech)}
                    disabled={approvingId === tech.id}
                    className="rounded-md bg-[var(--primary)] px-3 py-[5px] text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50"
                  >
                    {approvingId === tech.id ? t("approving") : t("approve")}
                  </button>
                ) : tech.status && tech.status !== "active" ? (
                  <span
                    className="rounded-full px-[10px] py-[3px] text-[12px] font-medium"
                    style={{
                      color: (ONBOARD_TONE[tech.status] ?? FALLBACK_BRAND).textColor,
                      backgroundColor: (ONBOARD_TONE[tech.status] ?? FALLBACK_BRAND).bgColor,
                    }}
                  >
                    {onboardLabel(tech.status)}
                  </span>
                ) : (
                  <Ellipsis className="h-5 w-5 text-[var(--text-secondary)]" />
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
