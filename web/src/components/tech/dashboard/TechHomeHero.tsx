"use client";

import { useEffect, useState } from "react";
import GoOnlineToggle from "./GoOnlineToggle";
import { useLocale, useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Availability = components["schemas"]["Technician"]["availability"];

const DOT_COLOR: Record<Availability, string> = {
  available: "#34D399",
  busy: "#FBBF24",
  offline: "#94A3B8",
  on_leave: "#94A3B8",
  circuit_breaker_open: "#F87171",
};

interface Props {
  /** 問候語（含姓名，父層已組好）。 */
  greeting: string;
  availability: Availability;
  /** 顯示金額（已格式化字串，如 "NT$ 12,400"）；無資料傳 null。 */
  amountLabel: string | null;
  /** 金額口徑說明（如「今日預估收入」）。 */
  amountCaption: string;
  onAvailabilityChanged: (next: Availability) => void;
}

/**
 * TechHomeHero — 首頁視覺錨點：問候 + 日期 + 上線狀態 + 收入 + 上線大開關
 * 收攏為單一深色漸層卡（取代舊「狀態膠囊 + 開關各佔半欄白卡」的鬆散 hero）。
 * 漸層色自含（固定深藍層次、白字），亮/暗主題下皆成立，不依賴主題變數。
 */
export default function TechHomeHero({
  greeting,
  availability,
  amountLabel,
  amountCaption,
  onAvailabilityChanged,
}: Props) {
  const t = useTranslations("techPortal.home.status");
  const { locale } = useLocale();

  // 日期於 mount 後才渲染：client component 仍會 SSR，直接 new Date() 會造成
  // server/client 時區差的 hydration mismatch。
  const [dateLabel, setDateLabel] = useState<string | null>(null);
  useEffect(() => {
    setDateLabel(
      new Intl.DateTimeFormat(locale === "en" ? "en-US" : "zh-TW", {
        month: "long",
        day: "numeric",
        weekday: "long",
      }).format(new Date()),
    );
  }, [locale]);

  return (
    <section className="relative overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#0F172A_0%,#1E3A8A_78%,#1D4ED8_100%)] p-5 text-white shadow-md md:p-6">
      {/* 裝飾光暈（單一、低調） */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-[#3B82F6] opacity-20 blur-3xl"
      />

      <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        {/* 左：問候 + 日期 + 收入 */}
        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-[20px] font-bold leading-tight md:text-[22px]">
                {greeting}
              </h2>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-[12px] font-medium text-white/90 ring-1 ring-inset ring-white/15">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: DOT_COLOR[availability] }}
                />
                {t(availability)}
              </span>
            </div>
            {/* 佔位維持高度，避免日期 mount 後版面跳動 */}
            <p className="min-h-[18px] text-[13px] text-white/60">
              {dateLabel ?? " "}
            </p>
          </div>

          <div className="flex flex-col">
            <span className="text-[30px] font-bold leading-none tracking-tight [font-variant-numeric:tabular-nums] md:text-[34px]">
              {amountLabel ?? "—"}
            </span>
            <span className="mt-1.5 text-[12px] text-white/60">{amountCaption}</span>
          </div>
        </div>

        {/* 右：上線大開關 */}
        <div className="w-full md:w-[300px] md:shrink-0">
          <GoOnlineToggle
            availability={availability}
            onChanged={onAvailabilityChanged}
            tone="hero"
          />
        </div>
      </div>
    </section>
  );
}
