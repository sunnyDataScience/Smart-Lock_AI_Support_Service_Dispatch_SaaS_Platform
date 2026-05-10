"use client";

import type { components } from "@/types/api.generated";
import { useTranslations } from "@/components/i18n/LocaleProvider";

type Urgency = components["schemas"]["Urgency"];

const URGENCY_TONE: Record<
  Urgency,
  { bg: string; color: string; pulse?: boolean; key: string } | null
> = {
  low: null,
  medium: { bg: "#F59E0B", color: "#FFFFFF", key: "mediumBadge" },
  high: { bg: "#EF4444", color: "#FFFFFF", pulse: true, key: "highBadge" },
};

export default function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  const t = useTranslations("urgency");
  const tone = URGENCY_TONE[urgency];
  if (!tone) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-[2px] text-[11px] font-bold ${
        tone.pulse ? "animate-pulse" : ""
      }`}
      style={{ backgroundColor: tone.bg, color: tone.color }}
    >
      {t(tone.key)}
    </span>
  );
}
