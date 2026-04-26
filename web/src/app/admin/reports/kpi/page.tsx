"use client";

import { useState } from "react";
import {
  RefreshCw,
  Calendar,
  ChevronDown,
  Download,
  Timer,
  Info,
  ArrowRight,
  Star,
  StarHalf,
  ThumbsDown,
} from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

const segments = [
  { label: "日", active: false },
  { label: "週", active: false },
  { label: "月", active: true },
  { label: "季", active: false },
];

interface FunnelRow {
  label: string;
  value: string;
  color: string;
  widthPercent: number;
}

const funnelRows: FunnelRow[] = [
  { label: "對話建立", value: "1,245（100%）", color: "#1E40AF", widthPercent: 100 },
  { label: "ProblemCard 產出", value: "892（71.6%）", color: "#2563EB", widthPercent: 72 },
  { label: "工單建立", value: "634（51%）", color: "#3B82F6", widthPercent: 51 },
  { label: "派出/接受", value: "589（47.3%）", color: "#06B6D4", widthPercent: 47 },
  { label: "完工", value: "523（42%）", color: "#10B981", widthPercent: 42 },
  { label: "滿意評價", value: "489（39.3%）", color: "#047857", widthPercent: 39 },
];

const conversionRates = ["71.6%", "71.1%", "92.9%", "88.8%", "93.5%"];
const conversionColors = ["#2563EB", "#2563EB", "#10B981", "#2563EB", "#10B981"];

interface SlaDonut {
  label: string;
  value: string;
  target: string;
  sweepAngle: number;
  color: string;
}

const slaData: SlaDonut[] = [
  { label: "接單 SLA", value: "96.2%", target: "目標 95%", sweepAngle: 96.2, color: "var(--status-success)" },
  { label: "到場 SLA", value: "91.8%", target: "目標 90%", sweepAngle: 91.8, color: "var(--status-success)" },
  { label: "完工 SLA", value: "88.5%", target: "目標 85%", sweepAngle: 88.5, color: "var(--status-success)" },
  { label: "回覆 SLA", value: "98.1%", target: "目標 98%", sweepAngle: 98.1, color: "var(--status-warning)" },
];

interface SlaBar {
  name: string;
  value: string;
  percent: number;
  color: string;
}

const slaBars: SlaBar[] = [
  { name: "王大明", value: "98.5%", percent: 98.5, color: "var(--status-success)" },
  { name: "李小華", value: "97.1%", percent: 97.1, color: "var(--status-success)" },
  { name: "張志偉", value: "95.3%", percent: 95.3, color: "var(--status-success)" },
  { name: "陳美玲", value: "93.8%", percent: 93.8, color: "var(--status-warning)" },
  { name: "林建宏", value: "92.4%", percent: 92.4, color: "var(--status-warning)" },
];

interface DisputeMetric {
  label: string;
  value: string;
  valueColor: string;
  barWidth: number;
  barColor: string;
}

const disputeLeft: DisputeMetric[] = [
  { label: "退款率", value: "2.8%", valueColor: "var(--status-warning)", barWidth: 28, barColor: "var(--status-warning)" },
  { label: "保固索賠率", value: "1.5%", valueColor: "var(--status-info)", barWidth: 15, barColor: "var(--status-info)" },
  { label: "爭議升級率", value: "0.8%", valueColor: "var(--status-success)", barWidth: 8, barColor: "var(--status-success)" },
];

const disputeRight: DisputeMetric[] = [
  { label: "返工率", value: "2.1%", valueColor: "var(--status-warning)", barWidth: 21, barColor: "var(--status-warning)" },
  { label: "FTFR 一次修好率", value: "94.2%", valueColor: "var(--status-success)", barWidth: 94, barColor: "var(--status-success)" },
];

function SlaRing({ item }: { item: SlaDonut }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const progress = (item.sweepAngle / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-[90px] w-[90px]">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50" cy="50" r={radius}
            fill="none" stroke="#E2E8F0" strokeWidth="11"
          />
          <circle
            cx="50" cy="50" r={radius}
            fill="none" stroke={item.color} strokeWidth="11"
            strokeDasharray={`${progress} ${circumference}`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold text-[var(--text-primary)]">
            {item.value}
          </span>
        </div>
      </div>
      <span className="text-xs text-[var(--text-primary)]">{item.label}</span>
      <span className="text-[11px] text-[var(--text-secondary)]">{item.target}</span>
    </div>
  );
}

export default function KpiDashboardPage() {
  const [activeSegment, setActiveSegment] = useState("月");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {/* Page Header */}
          <div className="flex flex-col gap-1">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 報表 &gt; KPI 儀表板
            </span>
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
                KPI 儀表板
              </h1>
              <button className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
                <RefreshCw className="h-4 w-4 text-[var(--text-secondary)]" />
              </button>
            </div>
            <span className="text-[13px] text-[var(--text-secondary)]">
              資料截至 2026-04-25 14:30（延遲 &lt; 5 分鐘）
            </span>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-3">
            <div className="flex rounded-lg bg-[#F1F5F9] p-[3px]">
              {segments.map((seg) => (
                <button
                  key={seg.label}
                  onClick={() => setActiveSegment(seg.label)}
                  className={`rounded-md px-[14px] py-[6px] text-[13px] ${
                    activeSegment === seg.label
                      ? "bg-[var(--primary)] font-medium text-white"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-[7px]">
              <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
                2025-05 ~ 2026-04
              </span>
            </button>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-[7px]">
              <span className="text-[13px] text-[var(--text-primary)]">切片：全部</span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>

            <div className="flex items-center gap-2">
              <div className="relative h-5 w-9 rounded-full bg-[var(--primary)]">
                <div className="absolute right-[2px] top-[2px] h-4 w-4 rounded-full bg-white" />
              </div>
              <span className="text-[13px] text-[var(--text-primary)]">與上期比較</span>
            </div>

            <div className="flex-1" />

            <button className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-[7px]">
              <Download className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">匯出報告</span>
            </button>

            <button className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-[14px] py-[7px]">
              <Timer className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">排程週/月報</span>
            </button>
          </div>

          {/* Conversion Funnel Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-[var(--text-primary)]">
                轉換漏斗
              </span>
              <Info className="h-4 w-4 text-[var(--text-disabled)]" />
            </div>

            <div className="flex flex-col gap-2">
              {funnelRows.map((row) => (
                <div
                  key={row.label}
                  className="flex h-9 items-center justify-between rounded-md px-3"
                  style={{
                    backgroundColor: row.color,
                    width: `${row.widthPercent}%`,
                  }}
                >
                  <span className="text-xs font-semibold text-white">{row.label}</span>
                  <span className="text-xs font-semibold text-white">{row.value}</span>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-center gap-[6px] pt-2">
              {conversionRates.map((rate, i) => (
                <div key={i} className="flex items-center gap-[6px]">
                  {i > 0 && <ArrowRight className="h-[14px] w-[14px] text-[var(--text-disabled)]" />}
                  <span
                    className="text-[11px] font-semibold"
                    style={{ color: conversionColors[i] }}
                  >
                    {rate}
                  </span>
                </div>
              ))}
            </div>
            <span className="text-center text-[11px] text-[var(--text-secondary)]">
              各階段轉換率
            </span>
          </div>

          {/* SLA Achievement Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              SLA 達成率
            </span>

            <div className="flex gap-6">
              <div className="flex flex-1 items-center justify-around">
                {slaData.map((item) => (
                  <SlaRing key={item.label} item={item} />
                ))}
              </div>

              <div className="flex flex-1 flex-col gap-3">
                <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                  Top 5 技師 SLA 達成率
                </span>
                {slaBars.map((bar) => (
                  <div key={bar.name} className="flex items-center gap-2">
                    <span className="w-14 text-xs text-[var(--text-primary)]">
                      {bar.name}
                    </span>
                    <div className="h-5 flex-1 rounded bg-[#E2E8F0]">
                      <div
                        className="h-5 rounded"
                        style={{
                          width: `${bar.percent}%`,
                          backgroundColor: bar.color,
                        }}
                      />
                    </div>
                    <span
                      className="text-xs font-semibold"
                      style={{ color: bar.color }}
                    >
                      {bar.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Customer Satisfaction Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              客戶滿意度
            </span>

            <div className="flex gap-4">
              {/* Star Rating */}
              <div className="flex flex-1 flex-col items-center gap-3 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <span className="text-[13px] text-[var(--text-secondary)]">平均星等</span>
                <span className="text-[28px] font-bold text-[var(--text-primary)]">
                  4.6 / 5.0
                </span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4].map((i) => (
                    <Star key={i} className="h-5 w-5 fill-[#F59E0B] text-[#F59E0B]" />
                  ))}
                  <StarHalf className="h-5 w-5 fill-[#F59E0B] text-[#F59E0B]" />
                </div>
              </div>

              {/* NPS */}
              <div className="flex flex-1 flex-col items-center gap-3 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <span className="text-[13px] text-[var(--text-secondary)]">NPS 淨推薦值</span>
                <span className="text-[28px] font-bold text-[var(--status-success)]">
                  +62
                </span>
                <div className="flex h-5 w-full overflow-hidden rounded">
                  <div className="bg-[var(--status-success)]" style={{ width: "64%" }} />
                  <div className="bg-[var(--status-warning)]" style={{ width: "24%" }} />
                  <div className="bg-[var(--status-danger)]" style={{ width: "12%" }} />
                </div>
                <div className="flex gap-3">
                  <span className="text-[10px] text-[var(--status-success)]">● 推薦者 64%</span>
                  <span className="text-[10px] text-[var(--status-warning)]">● 被動者 24%</span>
                  <span className="text-[10px] text-[var(--status-danger)]">● 貶損者 12%</span>
                </div>
              </div>

              {/* Bad Review */}
              <div className="flex flex-1 flex-col items-center gap-3 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <span className="text-[13px] text-[var(--text-secondary)]">差評率</span>
                <span className="text-[28px] font-bold text-[var(--status-success)]">
                  3.2%
                </span>
                <span className="text-xs text-[var(--text-secondary)]">共 17 則差評</span>
                <ThumbsDown className="h-6 w-6 text-[var(--text-disabled)]" />
              </div>
            </div>
          </div>

          {/* Dispute & Anomaly Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              爭議與異常率
            </span>
            <div className="flex gap-4">
              <div className="flex flex-1 flex-col gap-4 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                {disputeLeft.map((m) => (
                  <div key={m.label} className="flex flex-col gap-[6px]">
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] text-[var(--text-primary)]">{m.label}</span>
                      <span className="text-[13px] font-semibold" style={{ color: m.valueColor }}>
                        {m.value}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded bg-[#E2E8F0]">
                      <div
                        className="h-2 rounded"
                        style={{ width: `${m.barWidth}%`, backgroundColor: m.barColor }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex flex-1 flex-col gap-4 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                {disputeRight.map((m) => (
                  <div key={m.label} className="flex flex-col gap-[6px]">
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] text-[var(--text-primary)]">{m.label}</span>
                      <span className="text-[13px] font-semibold" style={{ color: m.valueColor }}>
                        {m.value}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded bg-[#E2E8F0]">
                      <div
                        className="h-2 rounded"
                        style={{ width: `${m.barWidth}%`, backgroundColor: m.barColor }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Technician Efficiency Card */}
          <div className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-6">
            <span className="text-base font-semibold text-[var(--text-primary)]">
              技師效率
            </span>

            <div className="flex gap-4">
              <div className="flex flex-1 flex-col items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <span className="text-[13px] text-[var(--text-secondary)]">平均處理時長</span>
                <span className="text-2xl font-bold text-[var(--text-primary)]">
                  2.4 小時
                </span>
                <span className="text-[11px] text-[var(--status-success)]">
                  ▼ 12% vs 上期
                </span>
              </div>
              <div className="flex flex-1 flex-col items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[#F8FAFC] p-5">
                <span className="text-[13px] text-[var(--text-secondary)]">
                  一次修好率（FTFR）
                </span>
                <span className="text-2xl font-bold text-[var(--status-success)]">
                  94.2%
                </span>
                <span className="text-[11px] text-[var(--status-success)]">
                  ▲ 3.1% vs 上期
                </span>
              </div>
            </div>

            {/* Scatter Plot */}
            <div className="relative h-[280px] rounded-[10px] border border-[var(--border)] bg-[#F8FAFC]">
              <span className="absolute left-2 top-[120px] -rotate-90 text-[10px] text-[var(--text-secondary)]">
                FTFR（%）
              </span>
              <span className="absolute bottom-4 right-[calc(50%-60px)] text-[10px] text-[var(--text-secondary)]">
                平均處理時長（小時）
              </span>

              {/* Cross lines */}
              <div className="absolute left-[50px] top-[140px] h-px w-[calc(100%-60px)] bg-[#CBD5E1]" />
              <div className="absolute left-[50%] top-5 h-[240px] w-px bg-[#CBD5E1]" />

              {/* Quadrant labels */}
              <span className="absolute left-[60px] top-7 text-[11px] font-semibold text-[var(--status-success)]">
                ⭐ 高效高質
              </span>
              <span className="absolute right-[60px] top-7 text-[11px] font-semibold text-[var(--status-warning)]">
                需加速
              </span>
              <span className="absolute bottom-7 right-[60px] text-[11px] font-semibold text-[var(--status-danger)]">
                需關注
              </span>
              <span className="absolute bottom-7 left-[60px] text-[11px] font-semibold text-[#3B82F6]">
                快但需提質
              </span>

              {/* Dots */}
              {[
                { x: "13%", y: "21%", color: "var(--status-success)" },
                { x: "20%", y: "27%", color: "var(--status-success)" },
                { x: "27%", y: "18%", color: "var(--status-success)" },
                { x: "33%", y: "32%", color: "var(--status-success)" },
                { x: "38%", y: "39%", color: "var(--status-success)" },
                { x: "16%", y: "64%", color: "#3B82F6" },
                { x: "24%", y: "71%", color: "#3B82F6" },
                { x: "65%", y: "25%", color: "var(--status-warning)" },
                { x: "74%", y: "36%", color: "var(--status-warning)" },
                { x: "71%", y: "68%", color: "var(--status-danger)" },
              ].map((dot, i) => (
                <div
                  key={i}
                  className="absolute h-3 w-3 rounded-full"
                  style={{
                    left: dot.x,
                    top: dot.y,
                    backgroundColor: dot.color,
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
