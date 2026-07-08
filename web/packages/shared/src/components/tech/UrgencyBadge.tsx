"use client";

import type { components } from "@shared/types/api.generated";
import { useTranslations } from "@shared/components/i18n/LocaleProvider";

type Urgency = components["schemas"]["Urgency"];

// 對齊設計 spec（11_tech_pool §urgency_badge）：一般單「不顯示」badge，
// 只有急迫單顯著標示。API urgency 三檔映射 DB priority：low→low、
// normal→medium、high/urgent→high（_DB_URGENCY_TO_API）。
// medium 即一般單 → 不顯示（原本誤標「急件」，普通單全部被標急件）。
// spec 的「Red Code」屬 emergency 檔，DB priority 尚無此值 → 待引入後再接。
const URGENCY_TONE: Record<
  Urgency,
  { bg: string; color: string; pulse?: boolean; key: string } | null
> = {
  low: null,
  medium: null,
  high: { bg: "#F59E0B", color: "#FFFFFF", pulse: true, key: "highBadge" },
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
