"use client";

import { use, useEffect, useState } from "react";
import { ChevronRight, Star } from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import TechnicianDetailSidebar from "@/components/technicians/TechnicianDetailSidebar";
import CertificationMatrix from "@/components/technicians/CertificationMatrix";
import { api, getCurrentSession, FALLBACK_TENANT_ID } from "@/lib/api";
import { friendlyError } from "@/lib/apiError";
import type { components } from "@/types/api.generated";

type Technician = components["schemas"]["Technician"];
type TechnicianEnvelope = components["schemas"]["TechnicianEnvelope"];
type Availability = Technician["availability"];

const AVAILABILITY_STYLE: Record<Availability, { label: string; textColor: string; bgColor: string }> = {
  available: { label: "可用", textColor: "#065F46", bgColor: "#D1FAE5" },
  busy: { label: "外出中", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  offline: { label: "離線", textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" },
  on_leave: { label: "休假中", textColor: "#92400E", bgColor: "#FEF3C7" },
  circuit_breaker_open: { label: "暫停派工", textColor: "#991B1B", bgColor: "#FEE2E2" },
};

const BRAND_STYLE: Record<string, { textColor: string; bgColor: string }> = {
  Yale: { textColor: "#92400E", bgColor: "#FEF3C7" },
  Chatlock: { textColor: "#3730A3", bgColor: "#E0E7FF" },
  美樂: { textColor: "#065F46", bgColor: "#D1FAE5" },
  "Mi-La": { textColor: "#065F46", bgColor: "#D1FAE5" },
  Dormakaba: { textColor: "#1E40AF", bgColor: "#DBEAFE" },
};

const FALLBACK_BRAND = { textColor: "var(--text-secondary)", bgColor: "var(--bg-page)" };

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return iso.slice(0, 10);
  } catch {
    return "—";
  }
}

function ProfileCard({ technician }: { technician: Technician }) {
  const ratingFloor = Math.floor(technician.rating);
  const completed = technician.completed_orders_count ?? 0;
  const region = (technician.service_areas ?? []).join("、") || "—";
  const skills = technician.skills ?? [];

  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
        個人資料
      </h2>
      <div className="flex gap-6">
        <div className="flex flex-col items-center gap-2">
          <div className="h-[80px] w-[80px] flex-shrink-0 rounded-full bg-[#DBEAFE]" />
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((i) => (
              <Star
                key={i}
                className={
                  i <= ratingFloor
                    ? "h-4 w-4 fill-[var(--accent)] text-[var(--accent)]"
                    : "h-4 w-4 text-[var(--border)]"
                }
              />
            ))}
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              {technician.rating.toFixed(1)}
            </span>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3">
          <div className="flex gap-4">
            <Field label="姓名" value={technician.name} />
            <Field label="電話" value={technician.phone} mono />
            <Field label="服務區域" value={region} />
          </div>
          <div className="flex gap-4">
            <Field label="入職日期" value={formatDate(technician.created_at)} />
            <Field label="等級" value={technician.level} />
            <Field
              label="完成工單"
              value={`${completed} 件`}
              color="var(--primary)"
              bold
            />
          </div>
          <div className="flex flex-col gap-[6px]">
            <span className="text-[12px] text-[var(--text-secondary)]">
              專長品牌
            </span>
            <div className="flex flex-wrap gap-[6px]">
              {skills.length > 0 ? (
                skills.map((b) => {
                  const style = BRAND_STYLE[b] ?? FALLBACK_BRAND;
                  return (
                    <span
                      key={b}
                      className="rounded-md px-3 py-1 text-[12px] font-medium"
                      style={{ color: style.textColor, backgroundColor: style.bgColor }}
                    >
                      {b}
                    </span>
                  );
                })
              ) : (
                <span className="text-[12px] text-[var(--text-disabled)]">—</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  color,
  bold,
  mono,
}: {
  label: string;
  value: string;
  color?: string;
  bold?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col gap-1">
      <span className="text-[12px] text-[var(--text-secondary)]">{label}</span>
      <span
        className={`text-[14px] ${bold ? "font-semibold" : "font-medium"} ${mono ? "font-['IBM_Plex_Mono']" : ""}`}
        style={{ color: color || "var(--text-primary)" }}
      >
        {value}
      </span>
    </div>
  );
}

/* ─── 本週排班（2026-07-02 起接真資料：getTechnicianScheduleV2）─── */

interface TechScheduleData {
  month: string;
  work_orders_per_day: Record<string, number>;
  leave_days: string[];
  standby_days: string[];
}

const WEEKDAY_LABELS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"];

function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function WeeklySchedule({ techId, tenantId }: { techId: string; tenantId: string }) {
  const [data, setData] = useState<Record<string, TechScheduleData>>({});
  const [error, setError] = useState<string | null>(null);

  // 本週（週一起算）：跨月時需抓兩個月份的排班資料
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const week = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
  const months = Array.from(
    new Set(week.map((d) => isoDate(d).slice(0, 7))),
  ).sort();
  const monthsKey = months.join(",");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const results = await Promise.all(
          monthsKey.split(",").map((m) =>
            api.get<TechScheduleData>(
              `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(techId)}/schedule?month=${m}`,
            ),
          ),
        );
        if (!cancelled) {
          setData(Object.fromEntries(results.map((r) => [r.month, r])));
        }
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [techId, tenantId, monthsKey]);

  const todayIso = isoDate(today);

  function dayCell(d: Date) {
    const iso = isoDate(d);
    const m = data[iso.slice(0, 7)];
    if (m?.leave_days.includes(iso))
      return { text: "休假", color: "#92400E", bg: "#FEF3C7" };
    if (m?.standby_days.includes(iso))
      return { text: "備勤", color: "#3730A3", bg: "#E0E7FF" };
    const n = m?.work_orders_per_day[iso] ?? 0;
    if (n > 0) return { text: `工單 ${n}`, color: "#1E40AF", bg: "#DBEAFE" };
    return {
      text: "無排班",
      color: "var(--text-disabled)",
      bg: "var(--bg-page)",
      border: true,
    };
  }

  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">本週排班</h2>
        <span className="text-[13px] text-[var(--text-secondary)]">
          {isoDate(week[0]).replaceAll("-", "/")} - {isoDate(week[6]).replaceAll("-", "/")}
        </span>
      </div>
      {error ? (
        <span className="text-[12px] text-red-600">{error}</span>
      ) : (
        <div className="flex gap-[6px]">
          {week.map((d, i) => {
            const cell = dayCell(d);
            const iso = isoDate(d);
            return (
              <div key={iso} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
                  {WEEKDAY_LABELS[i]}
                </span>
                <span
                  className="text-[11px]"
                  style={{ color: iso === todayIso ? "var(--primary)" : "var(--text-secondary)" }}
                >
                  {d.getDate()}
                </span>
                <div
                  className="flex h-12 w-full items-center justify-center rounded-md"
                  style={{
                    backgroundColor: cell.bg,
                    border: cell.border ? "1px solid var(--border)" : undefined,
                  }}
                >
                  <span className="text-[11px] font-medium" style={{ color: cell.color }}>
                    {cell.text}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

/* ─── Main Page ─────────────────────────────────────────────── */

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function TechnicianDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const [technician, setTechnician] = useState<Technician | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // CR-0002-α：遷移至 tenant-scoped v2 端點
  const session = getCurrentSession();
  const tenantId = session?.tenantId ?? FALLBACK_TENANT_ID;

  async function loadTechnician() {
    setError(null);
    try {
      const res = await api.get<TechnicianEnvelope>(
        `/tenants/${encodeURIComponent(tenantId)}/technicians/${encodeURIComponent(id)}`,
      );
      setTechnician(res.data ?? null);
    } catch (e) {
      setError(
        friendlyError(e),
      );
    }
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      await loadTechnician();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, tenantId]);

  // CR-0114:師傅身分歸平台方 —— 生命週期(核准/停權/復權/終止)與主檔編輯
  // (姓名/技能/區域/等級)、認證管理皆由 platform console 操作;本頁完全唯讀。

  const status = technician
    ? AVAILABILITY_STYLE[technician.availability] ?? AVAILABILITY_STYLE.available
    : null;
  const shortId = id.slice(0, 8);

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-y-auto">
          {/* Header */}
          <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] pl-14 pr-4 md:px-8 py-4">
            <div className="flex items-center gap-[6px]">
              <Link href="/technicians" className="text-[13px] text-[var(--primary)] hover:underline">
                技師管理
              </Link>
              <ChevronRight className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                {technician?.name ?? shortId}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
                  {loading && !technician ? "載入中…" : technician?.name ?? "—"}
                </h1>
                {status && (
                  <span
                    className="rounded-full px-3 py-1 text-[12px] font-medium"
                    style={{ color: status.textColor, backgroundColor: status.bgColor }}
                  >
                    {status.label}
                  </span>
                )}
                <span className="font-['IBM_Plex_Mono'] text-[13px] text-[var(--text-secondary)]" title={id}>
                  ID: {shortId}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {/* CR-0114:編輯/停權/復權/終止皆歸平台方 console,品牌端唯讀。 */}
                <span className="flex items-center text-[12px] text-[var(--text-secondary)]">
                  師傅資料與生命週期由平台方管理
                </span>
              </div>
            </div>
          </div>

          {error && (
            <div className="mx-8 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              載入技師失敗：{error}
            </div>
          )}

          {technician ? (
            <>
              <ProfileCard technician={technician} />
              <CertificationMatrix tenantId={tenantId} technicianId={id} />
              <WeeklySchedule techId={id} tenantId={tenantId} />
            </>
          ) : (
            !loading && !error && (
              <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-secondary)]">
                找不到此技師
              </div>
            )
          )}
        </div>

        <TechnicianDetailSidebar technicianId={id} availability={technician?.availability} />
      </div>
    </div>
  );
}
