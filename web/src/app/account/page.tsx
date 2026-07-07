"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Bell,
  CalendarDays,
  ChevronRight,
  CircleUser,
  LogOut,
  ShieldCheck,
  Star,
  Wrench,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { useTranslations } from "@/components/i18n/LocaleProvider";
import { api, auth, getCurrentSession, logout } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];

const AVAILABILITY_COLOR: Record<Technician["availability"], string> = {
  available: "#10B981",
  busy: "#F59E0B",
  offline: "#94A3B8",
  on_leave: "#94A3B8",
  circuit_breaker_open: "#EF4444",
};

function formatErr(e: unknown): string {
  return friendlyError(e);
}

export default function AccountPage() {
  const router = useRouter();
  const t = useTranslations("pages.account.profile");
  const tAvail = useTranslations("pages.account.profile.availability");
  const tShell = useTranslations("techPortal.shell");
  const [tech, setTech] = useState<Technician | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState(true);
  const [loggingOut, setLoggingOut] = useState(false);

  const session = getCurrentSession();

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<TechnicianEnvelope>("/api/v1/technicians/me");
      const data = res.data;
      setTech(data ?? null);
      if (data) {
        setOnline(data.availability === "available");
      }
    } catch (e) {
      setError(formatErr(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  async function toggleOnline() {
    // PATCH /api/v1/technicians/me/availability（available↔offline）
    const next = online ? "offline" : "available";
    setOnline(!online); // 樂觀更新
    try {
      await api.patch("/api/v1/technicians/me/availability", { online_state: next });
      setTech((prev) => (prev ? { ...prev, availability: next } : prev));
    } catch (e) {
      setOnline(online); // 回滾
      setError(formatErr(e));
    }
  }

  async function handleLogout() {
    if (loggingOut) return;
    if (!window.confirm(t("logoutConfirm"))) return;
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      auth.clear();
    } finally {
      router.replace("/tech-login");
    }
  }

  const displayName = tech?.name ?? session?.email ?? t("fallbackName");
  const availability = tech?.availability ?? "offline";
  const availColor = AVAILABILITY_COLOR[availability];
  const availLabel = tAvail(availability);

  return (
    <TechShell
      wide
      // 頁首交由 shell 滿寬渲染（修大螢幕「浮動白條」跑版;label 複用底欄「帳戶」）
      header={
        <div className="flex items-center px-4 py-3 md:px-6">
          <h1 className="text-[18px] font-semibold text-[var(--text-primary)]">
            {tShell("bottomNav.account")}
          </h1>
        </div>
      }
    >
      {/* profile_header — 漸層背景(soft UI 改版:teal 系對齊 .tech-soft 主色) */}
      <div
        className="px-4 pt-6 pb-8 text-white"
        style={{
          background: "linear-gradient(180deg, #0F766E 0%, #134E4A 100%)",
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-white/40 bg-white/15 backdrop-blur">
            <span className="text-[24px] font-bold">
              {displayName.slice(0, 1).toUpperCase()}
            </span>
          </div>
          <div className="flex flex-1 flex-col">
            <span className="text-[18px] font-semibold">{displayName}</span>
            <span className="text-[12px] opacity-80">
              {tech ? `T-${tech.id.slice(0, 6).toUpperCase()}` : "—"}
            </span>
            <div className="mt-1 inline-flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: availColor }}
              />
              <span className="text-[12px] opacity-90">{availLabel}</span>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between rounded-xl bg-white/15 px-3 py-2 backdrop-blur">
          <div className="flex flex-col">
            <span className="text-[12px] opacity-90">{t("onlineToggleLabel")}</span>
            <span className="text-[10px] opacity-70">
              {t("onlineToggleHint")}
            </span>
          </div>
          <button
            type="button"
            onClick={toggleOnline}
            className="relative h-7 w-12 rounded-full transition"
            style={{
              backgroundColor: online ? "#10B981" : "rgba(255,255,255,0.3)",
            }}
            aria-label={t("ariaToggleOnline")}
          >
            <span
              className="absolute top-[2px] h-6 w-6 rounded-full bg-[var(--bg-surface)] shadow transition-all"
              style={{ left: online ? "22px" : "2px" }}
            />
          </button>
        </div>
      </div>

      {error && (
        <div className="m-4 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      {/* 桌面：內容區改 2 欄吃滿寬度（手機維持單欄堆疊）*/}
      <div className="md:grid md:grid-cols-2 md:items-start md:gap-x-4 md:px-2">
      {/* income_overview / performance_dashboard — MVP 顯示骨架 */}
      <section className="mx-4 mt-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          {t("monthIncome")}
        </span>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-[30px] font-bold text-[var(--text-primary)]">
            —
          </span>
          <span className="text-[12px] text-[var(--text-disabled)]">NT$</span>
        </div>
        <p className="mt-1 text-[11px] text-[var(--text-disabled)]">
          {t("incomeNote")}
        </p>
      </section>

      <section className="mx-4 mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-3 text-center shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
          <Wrench className="mx-auto h-4 w-4 text-[var(--text-secondary)]" />
          <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
            {tech?.completed_orders_count ?? "—"}
          </span>
          <span className="text-[10px] text-[var(--text-disabled)]">
            {t("completedOrders")}
          </span>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-3 text-center shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
          <Star className="mx-auto h-4 w-4 fill-amber-400 text-amber-400" />
          <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
            {tech?.rating != null ? tech.rating.toFixed(1) : "—"}
          </span>
          <span className="text-[10px] text-[var(--text-disabled)]">
            {t("rating")}
          </span>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-3 text-center shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
          <ShieldCheck className="mx-auto h-4 w-4 text-[var(--text-secondary)]" />
          <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
            {tech?.level ?? "—"}
          </span>
          <span className="text-[10px] text-[var(--text-disabled)]">{t("level")}</span>
        </div>
      </section>

      {/* profile_section */}
      <section className="mx-4 mt-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
        <span className="mb-2 block text-[11px] font-medium text-[var(--text-secondary)]">
          {t("personal")}
        </span>
        {loading && !tech ? (
          <div className="text-[12px] text-[var(--text-disabled)]">
            {t("loading")}
          </div>
        ) : tech ? (
          <div className="flex flex-col gap-2 text-[13px]">
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">{t("phone")}</span>
              <span className="font-medium text-[var(--text-primary)]">
                {tech.phone || "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">{t("skills")}</span>
              <span className="text-right font-medium text-[var(--text-primary)] line-clamp-1">
                {tech.skills.length > 0 ? tech.skills.join(", ") : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">{t("serviceArea")}</span>
              <span className="text-right font-medium text-[var(--text-primary)] line-clamp-1">
                {tech.service_areas.length > 0
                  ? tech.service_areas.join(", ")
                  : "—"}
              </span>
            </div>
          </div>
        ) : (
          <div className="text-[12px] text-[var(--text-disabled)]">
            {t("noProfile")}
          </div>
        )}
      </section>

      {/* appearance_section — 主題切換（技師端深色模式入口）*/}
      <section className="mx-4 mt-4 rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] p-4 shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
        <span className="mb-2 block text-[11px] font-medium text-[var(--text-secondary)]">
          {t("appearance")}
        </span>
        <ThemeToggle variant="segmented" />
      </section>

      {/* settings_section */}
      <section className="mx-4 mt-4 mb-6 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] shadow-[var(--tech-shadow-sm,0_1px_2px_rgba(0,0,0,0.05))]">
        <Link
          href="/account/schedule"
          className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-page)]"
        >
          <div className="flex items-center gap-3">
            <CalendarDays className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[14px] font-medium text-[var(--text-primary)]">
              {t("mySchedule")}
            </span>
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
        </Link>
        <div className="border-t border-[var(--border)]" />
        <button
          type="button"
          disabled
          className="flex w-full items-center justify-between px-4 py-3 text-left opacity-50"
        >
          <div className="flex items-center gap-3">
            <Bell className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[14px] font-medium text-[var(--text-primary)]">
              {t("notifPref")}
            </span>
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
        </button>
        <div className="border-t border-[var(--border)]" />
        <button
          type="button"
          disabled
          className="flex w-full items-center justify-between px-4 py-3 text-left opacity-50"
        >
          <div className="flex items-center gap-3">
            <CircleUser className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[14px] font-medium text-[var(--text-primary)]">
              {t("editProfile")}
            </span>
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
        </button>
        <div className="border-t border-[var(--border)]" />
        <button
          type="button"
          onClick={handleLogout}
          disabled={loggingOut}
          className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-page)] disabled:opacity-50"
        >
          <div className="flex items-center gap-3">
            <LogOut className="h-4 w-4 text-red-600" />
            <span className="text-[14px] font-medium text-red-600">
              {loggingOut ? t("loggingOut") : t("logout")}
            </span>
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
        </button>
      </section>
      </div>

      <p className="px-4 pb-4 text-center text-[10px] text-[var(--text-disabled)]">
        {t("footer")}
      </p>
    </TechShell>
  );
}
