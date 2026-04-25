"use client";

import {
  ChevronRight,
  Pencil,
  Ban,
  Star,
} from "lucide-react";
import Link from "next/link";
import Sidebar from "@/components/layout/Sidebar";
import TechnicianDetailSidebar from "@/components/technicians/TechnicianDetailSidebar";

/* ─── Profile Card ─── */

interface ProfileField {
  label: string;
  value: string;
  color?: string;
  bold?: boolean;
}

const profileRow1: ProfileField[] = [
  { label: "姓名", value: "陳建宏" },
  { label: "電話", value: "0912-345-678" },
  { label: "Email", value: "chen.jh@mail.com" },
];

const profileRow2: ProfileField[] = [
  { label: "服務區域", value: "台北市、新北市" },
  { label: "入職日期", value: "2022-03-15" },
  { label: "完成工單", value: "342 件", color: "var(--primary)", bold: true },
];

const brands = [
  { name: "Yale", textColor: "#92400E", bgColor: "#FEF3C7" },
  { name: "Samsung", textColor: "#1E40AF", bgColor: "#DBEAFE" },
  { name: "Gateman", textColor: "#3730A3", bgColor: "#E0E7FF" },
];

function ProfileCard() {
  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
        個人資料
      </h2>
      <div className="flex gap-6">
        {/* Avatar + Rating */}
        <div className="flex flex-col items-center gap-2">
          <div className="h-[80px] w-[80px] flex-shrink-0 rounded-full bg-[#DBEAFE]" />
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4].map((i) => (
              <Star
                key={i}
                className="h-4 w-4 fill-[var(--accent)] text-[var(--accent)]"
              />
            ))}
            <Star className="h-4 w-4 text-[var(--border)]" />
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              4.8
            </span>
          </div>
        </div>

        {/* Info Grid */}
        <div className="flex flex-1 flex-col gap-3">
          {/* Row 1 */}
          <div className="flex gap-4">
            {profileRow1.map((f) => (
              <div key={f.label} className="flex flex-1 flex-col gap-1">
                <span className="text-[12px] text-[var(--text-secondary)]">
                  {f.label}
                </span>
                <span className="text-[14px] font-medium text-[var(--text-primary)]">
                  {f.value}
                </span>
              </div>
            ))}
          </div>

          {/* Row 2 */}
          <div className="flex gap-4">
            {profileRow2.map((f) => (
              <div key={f.label} className="flex flex-1 flex-col gap-1">
                <span className="text-[12px] text-[var(--text-secondary)]">
                  {f.label}
                </span>
                <span
                  className={`text-[14px] ${f.bold ? "font-semibold" : "font-medium"}`}
                  style={{ color: f.color || "var(--text-primary)" }}
                >
                  {f.value}
                </span>
              </div>
            ))}
          </div>

          {/* Brands */}
          <div className="flex flex-col gap-[6px]">
            <span className="text-[12px] text-[var(--text-secondary)]">
              專長品牌
            </span>
            <div className="flex gap-[6px]">
              {brands.map((b) => (
                <span
                  key={b.name}
                  className="rounded-md px-3 py-1 text-[12px] font-medium"
                  style={{ color: b.textColor, backgroundColor: b.bgColor }}
                >
                  {b.name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─── Skill Matrix ─── */

interface SkillRow {
  name: string;
  brand: string;
  obtainDate: string;
  expireDate: string;
  expireDateColor?: string;
  status: { label: string; textColor: string; bgColor: string };
}

const skills: SkillRow[] = [
  {
    name: "電子鎖安裝認證",
    brand: "Yale",
    obtainDate: "2023-06-15",
    expireDate: "2025-06-15",
    status: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" },
  },
  {
    name: "智慧門鎖維修",
    brand: "Samsung",
    obtainDate: "2023-09-20",
    expireDate: "2025-09-20",
    status: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" },
  },
  {
    name: "指紋辨識模組",
    brand: "Gateman",
    obtainDate: "2024-01-10",
    expireDate: "2026-01-10",
    status: { label: "有效", textColor: "#065F46", bgColor: "#D1FAE5" },
  },
  {
    name: "WiFi 模組更換",
    brand: "Yale",
    obtainDate: "2023-03-05",
    expireDate: "2025-03-05",
    expireDateColor: "var(--warning)",
    status: { label: "即將到期", textColor: "#92400E", bgColor: "#FEF3C7" },
  },
  {
    name: "藍牙配對認證",
    brand: "Samsung",
    obtainDate: "2022-11-20",
    expireDate: "2024-11-20",
    expireDateColor: "var(--error)",
    status: { label: "已過期", textColor: "#991B1B", bgColor: "#FEE2E2" },
  },
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
        {/* Header */}
        <div className="flex h-[40px] items-center bg-[var(--bg-page)] px-4">
          {skillColumns.map((col) => (
            <div key={col.label} className={`flex items-center ${col.width}`}>
              <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
                {col.label}
              </span>
            </div>
          ))}
        </div>

        {/* Rows */}
        {skills.map((s, idx) => (
          <div
            key={s.name}
            className={`flex h-[44px] items-center px-4 ${
              idx < skills.length - 1
                ? "border-b border-[var(--border)]"
                : ""
            }`}
          >
            <div className="flex w-[160px] items-center">
              <span className="text-[13px] text-[var(--text-primary)]">
                {s.name}
              </span>
            </div>
            <div className="flex w-[100px] items-center">
              <span className="text-[13px] text-[var(--text-primary)]">
                {s.brand}
              </span>
            </div>
            <div className="flex w-[100px] items-center">
              <span className="text-[13px] text-[var(--text-primary)]">
                {s.obtainDate}
              </span>
            </div>
            <div className="flex w-[100px] items-center">
              <span
                className="text-[13px]"
                style={{ color: s.expireDateColor || "var(--text-primary)" }}
              >
                {s.expireDate}
              </span>
            </div>
            <div className="flex flex-1 items-center">
              <span
                className="rounded-full px-[10px] py-[2px] text-[11px] font-medium"
                style={{
                  color: s.status.textColor,
                  backgroundColor: s.status.bgColor,
                }}
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

/* ─── Weekly Schedule ─── */

interface ScheduleDay {
  dayLabel: string;
  date: string;
  shift: string;
  shiftTextColor: string;
  bgColor: string;
  isToday?: boolean;
  hasBorder?: boolean;
}

const scheduleDays: ScheduleDay[] = [
  { dayLabel: "週一", date: "20", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週二", date: "21", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週三", date: "22", shift: "晚班", shiftTextColor: "#3730A3", bgColor: "#E0E7FF", isToday: true },
  { dayLabel: "週四", date: "23", shift: "晚班", shiftTextColor: "#3730A3", bgColor: "#E0E7FF" },
  { dayLabel: "週五", date: "24", shift: "早班", shiftTextColor: "#1E40AF", bgColor: "#DBEAFE" },
  { dayLabel: "週六", date: "25", shift: "值班", shiftTextColor: "#92400E", bgColor: "#FEF3C7" },
  { dayLabel: "週日", date: "26", shift: "休息", shiftTextColor: "var(--text-disabled)", bgColor: "var(--bg-page)", hasBorder: true },
];

const legendItems = [
  { label: "早班 08-16", color: "#DBEAFE" },
  { label: "晚班 14-22", color: "#E0E7FF" },
  { label: "值班 on-call", color: "#FEF3C7" },
  { label: "休息", color: "var(--bg-page)" },
];

function WeeklySchedule() {
  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      {/* Title Row */}
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
          本週排班
        </h2>
        <span className="text-[13px] text-[var(--text-secondary)]">
          2026/04/20 - 2026/04/26
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4">
        {legendItems.map((item) => (
          <div key={item.label} className="flex items-center gap-1">
            <div
              className="h-3 w-3 rounded-[3px]"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[11px] text-[var(--text-secondary)]">
              {item.label}
            </span>
          </div>
        ))}
      </div>

      {/* Grid */}
      <div className="flex gap-[6px]">
        {scheduleDays.map((d) => (
          <div
            key={d.dayLabel}
            className="flex flex-1 flex-col items-center gap-1"
          >
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {d.dayLabel}
            </span>
            <span
              className="text-[11px]"
              style={{
                color: d.isToday
                  ? "var(--primary)"
                  : "var(--text-secondary)",
              }}
            >
              {d.date}
            </span>
            <div
              className="flex h-12 w-full items-center justify-center rounded-md"
              style={{
                backgroundColor: d.bgColor,
                border: d.hasBorder
                  ? "1px solid var(--border)"
                  : undefined,
              }}
            >
              <span
                className="text-[11px] font-medium"
                style={{ color: d.shiftTextColor }}
              >
                {d.shift}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ─── Performance Charts ─── */

const barHeights = [45, 62, 55, 70, 58, 80];
const months = ["11月", "12月", "1月", "2月", "3月", "4月"];

function BarChart() {
  return (
    <div className="flex flex-1 flex-col gap-3 rounded-lg border border-[var(--border)] p-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          完成工單趨勢
        </span>
        <span className="text-[11px] text-[var(--text-secondary)]">
          近 6 個月
        </span>
      </div>
      <div className="flex h-[100px] items-end gap-2 pb-4">
        {barHeights.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-t"
            style={{
              height: h,
              backgroundColor:
                i === barHeights.length - 1
                  ? "var(--primary)"
                  : "var(--primary-light)",
            }}
          />
        ))}
      </div>
      <div className="flex justify-between">
        {months.map((m, i) => (
          <span
            key={m}
            className={`text-[10px] ${
              i === months.length - 1
                ? "font-semibold text-[var(--text-primary)]"
                : "text-[var(--text-disabled)]"
            }`}
          >
            {m}
          </span>
        ))}
      </div>
    </div>
  );
}

function LineChart() {
  return (
    <div className="flex flex-1 flex-col gap-3 rounded-lg border border-[var(--border)] p-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          客戶評分趨勢
        </span>
        <span className="text-[11px] text-[var(--text-secondary)]">
          近 6 個月
        </span>
      </div>
      <div className="relative h-[100px]">
        <svg
          viewBox="0 0 240 80"
          className="h-full w-full"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563EB" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0,50 Q40,40 80,35 T160,20 Q200,15 240,10 V80 H0 Z"
            fill="url(#lineGrad)"
          />
          <path
            d="M0,50 Q40,40 80,35 T160,20 Q200,15 240,10"
            fill="none"
            stroke="var(--primary)"
            strokeWidth="2"
          />
        </svg>
        <div className="absolute right-[40px] top-[8px] flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-[var(--primary)]" />
          <span className="text-[12px] font-semibold text-[var(--primary)]">
            4.8
          </span>
        </div>
      </div>
      <div className="flex justify-between">
        {months.map((m, i) => (
          <span
            key={m}
            className={`text-[10px] ${
              i === months.length - 1
                ? "font-semibold text-[var(--text-primary)]"
                : "text-[var(--text-disabled)]"
            }`}
          >
            {m}
          </span>
        ))}
      </div>
    </div>
  );
}

function DonutGauge({
  value,
  label,
  color,
  details,
  target,
}: {
  value: string;
  label: string;
  color: string;
  details: { dotColor: string; text: string }[];
  target: string;
}) {
  const numVal = parseFloat(value);
  const circumference = 2 * Math.PI * 36;
  const dashArray = (numVal / 100) * circumference;

  return (
    <div className="flex flex-1 flex-col gap-3 rounded-lg border border-[var(--border)] p-4">
      <span className="text-[13px] font-semibold text-[var(--text-primary)]">
        {label}
      </span>
      <div className="flex items-center gap-4">
        {/* Donut */}
        <div className="relative h-[80px] w-[80px] flex-shrink-0">
          <svg viewBox="0 0 80 80" className="h-full w-full">
            <circle
              cx="40"
              cy="40"
              r="36"
              fill="none"
              stroke="var(--border)"
              strokeWidth="6"
            />
            <circle
              cx="40"
              cy="40"
              r="36"
              fill="none"
              stroke={color}
              strokeWidth="6"
              strokeDasharray={`${dashArray} ${circumference}`}
              strokeLinecap="round"
              transform="rotate(-90 40 40)"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span
              className="text-[16px] font-bold"
              style={{ color }}
            >
              {value}
            </span>
          </div>
        </div>

        {/* Details */}
        <div className="flex flex-col gap-2">
          {details.map((d) => (
            <div key={d.text} className="flex items-center gap-[6px]">
              <div
                className="h-2 w-2 rounded"
                style={{ backgroundColor: d.dotColor }}
              />
              <span className="text-[12px] text-[var(--text-secondary)]">
                {d.text}
              </span>
            </div>
          ))}
          <span className="text-[11px] text-[var(--text-disabled)]">
            {target}
          </span>
        </div>
      </div>
    </div>
  );
}

function PerformanceCharts() {
  return (
    <section className="flex flex-col gap-4 bg-[var(--bg-surface)] px-8 py-6">
      <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">
        績效數據
      </h2>
      <div className="flex flex-col gap-4">
        {/* Row 1: Bar + Line */}
        <div className="flex gap-4">
          <BarChart />
          <LineChart />
        </div>
        {/* Row 2: Donut gauges */}
        <div className="flex gap-4">
          <DonutGauge
            value="3.2%"
            label="拒絕率"
            color="var(--success)"
            details={[
              { dotColor: "var(--success)", text: "已接受 96.8%" },
              { dotColor: "var(--error)", text: "已拒絕 3.2%" },
            ]}
            target="目標 < 5%"
          />
          <DonutGauge
            value="94%"
            label="準時到達率"
            color="var(--primary)"
            details={[
              { dotColor: "var(--primary)", text: "準時 94%" },
              { dotColor: "var(--warning)", text: "遲到 6%" },
            ]}
            target="目標 > 90%"
          />
        </div>
      </div>
    </section>
  );
}

/* ─── Main Page ─── */

export default function TechnicianDetailPage() {
  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Content */}
        <div className="flex flex-1 flex-col overflow-y-auto">
          {/* Header */}
          <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-[var(--bg-surface)] px-8 py-4">
            {/* Breadcrumb */}
            <div className="flex items-center gap-[6px]">
              <Link
                href="/technicians"
                className="text-[13px] text-[var(--primary)] hover:underline"
              >
                技師管理
              </Link>
              <ChevronRight className="h-[14px] w-[14px] text-[var(--text-disabled)]" />
              <span className="text-[13px] text-[var(--text-secondary)]">
                陳建宏
              </span>
            </div>

            {/* Header Row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h1 className="text-[22px] font-bold text-[var(--text-primary)]">
                  陳建宏
                </h1>
                <span className="rounded-full bg-[#D1FAE5] px-3 py-1 text-[12px] font-medium text-[#065F46]">
                  可用
                </span>
                <span className="text-[13px] text-[var(--text-secondary)]">
                  ID: T-0042
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] px-4 py-2">
                  <Pencil className="h-[14px] w-[14px] text-[var(--text-secondary)]" />
                  <span className="text-[13px] text-[var(--text-primary)]">
                    編輯
                  </span>
                </button>
                <button className="flex items-center gap-[6px] rounded-lg border border-[var(--error)] px-4 py-2">
                  <Ban className="h-[14px] w-[14px] text-[var(--error)]" />
                  <span className="text-[13px] text-[var(--error)]">停權</span>
                </button>
              </div>
            </div>
          </div>

          {/* Sections */}
          <ProfileCard />
          <SkillMatrix />
          <WeeklySchedule />
          <PerformanceCharts />
        </div>

        {/* Right Sidebar */}
        <TechnicianDetailSidebar />
      </div>
    </div>
  );
}
