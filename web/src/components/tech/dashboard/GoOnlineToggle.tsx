"use client";

import { useState } from "react";
import { Power, Loader2, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import type { components } from "@/types/api.generated";

type Availability = components["schemas"]["Technician"]["availability"];

interface Props {
  availability: Availability;
  /** 切換成功後回傳新狀態給父層更新（膠囊等共用顯示）。 */
  onChanged: (next: Availability) => void;
  /** hero＝嵌在深色漸層卡內（提示/錯誤文字改白系）；預設 card＝白底卡。 */
  tone?: "card" | "hero";
}

/**
 * GoOnlineToggle — 決策屏主行動：上線/離線大開關。
 * 接真實端點 PATCH /api/v1/technicians/me/availability（only available↔offline）。
 * busy / on_leave 顯示唯讀狀態；circuit_breaker_open 鎖定不可手動上線。
 */
export default function GoOnlineToggle({ availability, onChanged, tone = "card" }: Props) {
  const t = useTranslations("techPortal.home.goOnline");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOnline = availability === "available";
  const locked = availability === "circuit_breaker_open";
  // busy / on_leave 屬系統/排班狀態，主開關不直接覆寫
  const readOnly = availability === "busy" || availability === "on_leave";

  async function toggle() {
    if (submitting || locked || readOnly) return;
    const next: Availability = isOnline ? "offline" : "available";
    setSubmitting(true);
    setError(null);
    try {
      await api.patch("/api/v1/technicians/me/availability", { online_state: next });
      onChanged(next);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  // hero（深色漸層底）時離線態改白底深字：深底上的灰鈕不夠醒目，
  // 「上線接案」是首頁第一行動，需為視覺最強元素。
  const heroOffline = tone === "hero" && !locked && !readOnly && !isOnline;
  const bg = locked
    ? "#EF4444"
    : isOnline
      ? "#10B981"
      : readOnly
        ? "#F59E0B"
        : heroOffline
          ? "#FFFFFF"
          : "#64748B";
  const fg = heroOffline ? "#0F172A" : "#FFFFFF";

  const label = locked
    ? t("locked")
    : submitting
      ? t("submitting")
      : readOnly
        ? t(availability) // busy / on_leave
        : isOnline
          ? t("online")
          : t("offline");

  const hint = locked
    ? t("lockedHint")
    : isOnline
      ? t("onlineHint")
      : readOnly
        ? t("readOnlyHint")
        : t("offlineHint");

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        disabled={submitting || locked || readOnly}
        aria-pressed={isOnline}
        className="flex min-h-[64px] w-full max-w-[360px] items-center justify-center gap-3 rounded-2xl px-6 text-[17px] font-bold shadow-sm transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-90"
        style={{ backgroundColor: bg, color: fg }}
      >
        {submitting ? (
          <Loader2 className="h-6 w-6 animate-spin" />
        ) : locked ? (
          <Lock className="h-6 w-6" />
        ) : (
          <Power className="h-6 w-6" />
        )}
        {label}
      </button>
      <p
        className={`text-center text-[12px] ${
          tone === "hero" ? "text-white/60" : "text-[var(--text-secondary)]"
        }`}
      >
        {hint}
      </p>
      {error && (
        <p
          className={`text-center text-[12px] ${
            tone === "hero" ? "text-red-300" : "text-red-600"
          }`}
        >
          {error}
        </p>
      )}
    </div>
  );
}
