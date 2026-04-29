"use client";

import { use, useEffect, useState } from "react";
import { ChevronRight, Pencil, Ban, Star, Info } from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import TechnicianDetailSidebar from "@/components/technicians/TechnicianDetailSidebar";
import { ApiError, api } from "@/lib/api";
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

/* ─── Mock Sections (banner declares it) ─────────────────────── */

const skills = [
  { name: "電子鎖安裝認證", brand: "Yale", obtainDate: "2023-06-15", expireDate: "2025-06-15", status: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" } },
  { name: "智慧門鎖維修", brand: "Samsung", obtainDate: "2023-09-20", expireDate: "2025-09-20", status: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" } },
  { name: "指紋辨識模組", brand: "Gateman", obtainDate: "2024-01-10", expireDate: "2026-01-10", status: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" } },
  { name: "WiFi 模組更換", brand: "Yale", obtainDate: "2023-03-05", expireDate: "2025-03-05", expireDateColor: "var(--warning)", status: { label: "即將到期", textColor: "#92400E", bgColor: "#FEF3C7" } },
  { name: "藍牙配對認證", brand: "Samsung", obtainDate: "2022-11-20", expireDate: "2024-11-20", expireDateColor: "var(--error)", status: { label: "已過期", textColor: "#991B1B", bgColor: "#FEE2E2" } },
];

const skillColumns = [
  { label: "認證項目", width: "w-[160px]" },
  { label: "品牌", width: "w-[100px]" },
  { label: "取得日期", width: "w-[100px]" },
  { label: "到期日期", width: "w-[100px]" },
  { label: "狀態", width: "flex-1" },
];

function SkillMatrix() {
  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
        技能認證矩陣
      </h2>
      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        <div className="flex h-[40px] items-center bg-[var(--bg-page)] px-4">
          {skillColumns.map((col) => (
            <div key={col.label} className={`flex items-center ${col.width}`}>
              <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
                {col.label}
              </span>
            </div>
          ))}
        </div>
        {skills.map((s, idx) => (
          <div
            key={s.name}
            className={`flex h-[44px] items-center px-4 ${idx < skills.length - 1 ? "border-b border-[var(--border)]" : ""}`}
          >
            <div className="flex w-[160px]"><span className="text-[13px] text-[var(--text-primary)]">{s.name}</span></div>
            <div className="flex w-[100px]"><span className="text-[13px] text-[var(--text-primary)]">{s.brand}</span></div>
            <div className="flex w-[100px]"><span className="text-[13px] text-[var(--text-primary)]">{s.obtainDate}</span></div>
            <div className="flex w-[100px]">
              <span className="text-[13px]" style={{ color: s.expireDateColor || "var(--text-primary)" }}>
                {s.expireDate}
              </span>
            </div>
            <div className="flex flex-1">
              <span
                className="rounded-full px-[10px] py-[2px] text-[11px] font-medium"
                style={{ color: s.status.textColor, backgroundColor: s.status.bgColor }}
              >
                {s.status.label}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

const scheduleDays = [
  { dayLabel: "週一", date: "20", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週二", date: "21", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週三", date: "22", shift: "晚班", shiftTextColor: "#3730A3", bgColor: "#E0E7FF", isToday: true },
  { dayLabel: "週四", date: "23", shift: "晚班", shiftTextColor: "#3730A3", bgColor: "#E0E7FF" },
  { dayLabel: "週五", date: "24", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週六", date: "25", shift: "值班", shiftTextColor: "#92400E", bgColor: "#FEF3C7" },
  { dayLabel: "週日", date: "26", shift: "休息", shiftTextColor: "var(--text-disabled)", bgColor: "var(--bg-page)", hasBorder: true },
];

function WeeklySchedule() {
  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">本週排班</h2>
        <span className="text-[13px] text-[var(--text-secondary)]">2026/04/20 - 2026/04/26</span>
      </div>
      <div className="flex gap-[6px]">
        {scheduleDays.map((d) => (
          <div key={d.dayLabel} className="flex flex-1 flex-col items-center gap-1">
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">{d.dayLabel}</span>
            <span className="text-[11px]" style={{ color: d.isToday ? "var(--primary)" : "var(--text-secondary)" }}>
              {d.date}
            </span>
            <div
              className="flex h-12 w-full items-center justify-center rounded-md"
              style={{
                backgroundColor: d.bgColor,
                border: d.hasBorder ? "1px solid var(--border)" : undefined,
              }}
            >
              <span className="text-[11px] font-medium" style={{ color: d.shiftTextColor }}>
                {d.shift}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function MockBanner() {
  return (
    <div className="mx-8 mt-4 flex items-start gap-2 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] px-4 py-3">
      <Info className="mt-[2px] h-4 w-4 flex-shrink-0 text-[var(--text-secondary)]" />
      <span className="text-[12px] text-[var(--text-secondary)]">
        以下「技能認證矩陣」、「本週排班」與右側「可用狀態 / 佣金摘要 / 獎懲紀錄」為示意，待認證/排班/結算模組接入後將顯示真實資料；右側「進行中工單」已連線真實資料。
      </span>
    </div>
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

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await api.get<TechnicianEnvelope>(
          `/api/v1/technicians/${encodeURIComponent(id)}`,
        );
        if (!cancelled) setTechnician(res.data ?? null);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.errorCode} (${e.status})：${e.message}`
            : e instanceof Error
              ? e.message
              : String(e),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

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
          <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
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
                <button
                  disabled
                  title="即將推出"
                  className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] px-4 py-2 opacity-60 cursor-not-allowed"
                >
                  <Pencil className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
                  <span className="text-[13px] text-[var(--text-primary)]">編輯</span>
                </button>
                <button
                  disabled
                  title="即將推出"
                  className="flex items-center gap-[6px] rounded-lg border border-[var(--error)] px-4 py-2 opacity-60 cursor-not-allowed"
                >
                  <Ban className="h-[14px] w-[14px] text-[var(--error)]" />
                  <span className="text-[13px] text-[var(--error)]">停權</span>
                </button>
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
              <MockBanner />
              <SkillMatrix />
              <WeeklySchedule />
            </>
          ) : (
            !loading && !error && (
              <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-secondary)]">
                找不到此技師
              </div>
            )
          )}
        </div>

        <TechnicianDetailSidebar technicianId={id} />
      </div>
    </div>
  );
}
