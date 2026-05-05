"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  ChevronRight,
  CircleUser,
  LogOut,
  ShieldCheck,
  Star,
  Wrench,
} from "lucide-react";
import TechShell from "@/components/tech/TechShell";
import { ApiError, api, auth, getCurrentSession, logout } from "@/lib/api";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];

const AVAILABILITY_LABEL: Record<Technician["availability"], string> = {
  available: "在線",
  busy: "忙碌中",
  offline: "離線",
  on_leave: "請假中",
  circuit_breaker_open: "暫停接單（熔斷）",
};

const AVAILABILITY_COLOR: Record<Technician["availability"], string> = {
  available: "#10B981",
  busy: "#F59E0B",
  offline: "#94A3B8",
  on_leave: "#94A3B8",
  circuit_breaker_open: "#EF4444",
};

function formatErr(e: unknown): string {
  return e instanceof ApiError
    ? `${e.errorCode} (${e.status})：${e.message}`
    : e instanceof Error
      ? e.message
      : String(e);
}

export default function AccountPage() {
  const router = useRouter();
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

  function toggleOnline() {
    // 後端目前無 PATCH /technicians/me/availability — 僅本地切換並提示
    setOnline((v) => !v);
  }

  async function handleLogout() {
    if (loggingOut) return;
    if (!window.confirm("確定要登出？")) return;
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      auth.clear();
    } finally {
      router.replace("/tech-login");
    }
  }

  const displayName = tech?.name ?? session?.email ?? "技師";
  const availability = tech?.availability ?? "offline";
  const availColor = AVAILABILITY_COLOR[availability];
  const availLabel = AVAILABILITY_LABEL[availability];

  return (
    <TechShell>
      {/* profile_header — 漸層背景 */}
      <div
        className="px-4 pt-6 pb-8 text-white"
        style={{
          background: "linear-gradient(180deg, #2563EB 0%, #1E40AF 100%)",
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
            <span className="text-[12px] opacity-90">在線接單</span>
            <span className="text-[10px] opacity-70">
              （後端 API 待補，當前為本地切換）
            </span>
          </div>
          <button
            type="button"
            onClick={toggleOnline}
            className="relative h-7 w-12 rounded-full transition"
            style={{
              backgroundColor: online ? "#10B981" : "rgba(255,255,255,0.3)",
            }}
            aria-label="切換在線/離線"
          >
            <span
              className="absolute top-[2px] h-6 w-6 rounded-full bg-white shadow transition-all"
              style={{ left: online ? "22px" : "2px" }}
            />
          </button>
        </div>
      </div>

      {error && (
        <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
          {error}
        </div>
      )}

      {/* income_overview / performance_dashboard — MVP 顯示骨架 */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          本月收入概覽（待後端 API）
        </span>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-[30px] font-bold text-[var(--text-primary)]">
            —
          </span>
          <span className="text-[12px] text-[var(--text-disabled)]">NT$</span>
        </div>
        <p className="mt-1 text-[11px] text-[var(--text-disabled)]">
          收入總覽、佣金組成、結算紀錄屬 V1.1 範圍
        </p>
      </section>

      <section className="mx-4 mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-xl border border-[var(--border)] bg-white p-3 text-center shadow-sm">
          <Wrench className="mx-auto h-4 w-4 text-[var(--text-secondary)]" />
          <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
            {tech?.completed_orders_count ?? "—"}
          </span>
          <span className="text-[10px] text-[var(--text-disabled)]">
            完成工單
          </span>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-white p-3 text-center shadow-sm">
          <Star className="mx-auto h-4 w-4 fill-amber-400 text-amber-400" />
          <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
            {tech?.rating != null ? tech.rating.toFixed(1) : "—"}
          </span>
          <span className="text-[10px] text-[var(--text-disabled)]">
            平均評分
          </span>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-white p-3 text-center shadow-sm">
          <ShieldCheck className="mx-auto h-4 w-4 text-[var(--text-secondary)]" />
          <span className="mt-1 block text-[16px] font-bold text-[var(--text-primary)]">
            {tech?.level ?? "—"}
          </span>
          <span className="text-[10px] text-[var(--text-disabled)]">分級</span>
        </div>
      </section>

      {/* profile_section */}
      <section className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
        <span className="mb-2 block text-[11px] font-medium text-[var(--text-secondary)]">
          個人資料
        </span>
        {loading && !tech ? (
          <div className="text-[12px] text-[var(--text-disabled)]">
            載入中…
          </div>
        ) : tech ? (
          <div className="flex flex-col gap-2 text-[13px]">
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">手機</span>
              <span className="font-medium text-[var(--text-primary)]">
                {tech.phone || "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">技能</span>
              <span className="text-right font-medium text-[var(--text-primary)] line-clamp-1">
                {tech.skills.length > 0 ? tech.skills.join(", ") : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">服務區域</span>
              <span className="text-right font-medium text-[var(--text-primary)] line-clamp-1">
                {tech.service_areas.length > 0
                  ? tech.service_areas.join(", ")
                  : "—"}
              </span>
            </div>
          </div>
        ) : (
          <div className="text-[12px] text-[var(--text-disabled)]">
            尚未取得個人資料
          </div>
        )}
      </section>

      {/* settings_section */}
      <section className="mx-4 mt-4 mb-6 overflow-hidden rounded-xl border border-[var(--border)] bg-white shadow-sm">
        <button
          type="button"
          disabled
          className="flex w-full items-center justify-between px-4 py-3 text-left opacity-50"
        >
          <div className="flex items-center gap-3">
            <Bell className="h-4 w-4 text-[var(--text-secondary)]" />
            <span className="text-[14px] font-medium text-[var(--text-primary)]">
              通知偏好
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
              編輯個人資料
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
              {loggingOut ? "登出中…" : "登出"}
            </span>
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--text-disabled)]" />
        </button>
      </section>

      <p className="px-4 pb-4 text-center text-[10px] text-[var(--text-disabled)]">
        Smart Lock 技師工作台 v0.1
      </p>
    </TechShell>
  );
}
