"use client";

import { useState } from "react";
import { Crown, ChevronDown, Download } from "lucide-react";
import Sidebar from "@/components/layout/Sidebar";

const segments = [
  { label: "本週", active: false },
  { label: "本月", active: true },
  { label: "本季", active: false },
  { label: "本年", active: false },
];

interface PodiumCard {
  rank: number;
  name: string;
  score: number;
  scoreColor: string;
  borderColor: string;
  avatarBg: string;
  completionRate: string;
  rating: string;
  turnaround: string;
  hasCrown: boolean;
}

const podium: PodiumCard[] = [
  {
    rank: 1,
    name: "陳大明",
    score: 96.5,
    scoreColor: "#FBBF24",
    borderColor: "#FBBF24",
    avatarBg: "#DBEAFE",
    completionRate: "98%",
    rating: "4.9",
    turnaround: "1.8hr",
    hasCrown: true,
  },
  {
    rank: 2,
    name: "林美玲",
    score: 94.2,
    scoreColor: "#64748B",
    borderColor: "#94A3B8",
    avatarBg: "#DBEAFE",
    completionRate: "96%",
    rating: "4.8",
    turnaround: "2.1hr",
    hasCrown: false,
  },
  {
    rank: 3,
    name: "張志豪",
    score: 91.8,
    scoreColor: "#D97706",
    borderColor: "#D97706",
    avatarBg: "#DBEAFE",
    completionRate: "94%",
    rating: "4.7",
    turnaround: "2.3hr",
    hasCrown: false,
  },
];

interface RankingRow {
  rank: number;
  name: string;
  avatarBg: string;
  orders: number;
  completionRate: number;
  rating: string;
  turnaround: string;
  rejectionRate: string;
  rejectionColor: string;
  revenue: string;
}

const rows: RankingRow[] = [
  { rank: 1, name: "陳大明", avatarBg: "#DBEAFE", orders: 87, completionRate: 98, rating: "4.9 ★", turnaround: "1.8hr", rejectionRate: "1.2%", rejectionColor: "var(--status-success)", revenue: "$128K" },
  { rank: 2, name: "林美玲", avatarBg: "#E0E7FF", orders: 82, completionRate: 96, rating: "4.8 ★", turnaround: "2.1hr", rejectionRate: "2.1%", rejectionColor: "var(--status-success)", revenue: "$119K" },
  { rank: 3, name: "張志豪", avatarBg: "#FEF3C7", orders: 79, completionRate: 94, rating: "4.7 ★", turnaround: "2.3hr", rejectionRate: "2.8%", rejectionColor: "var(--status-success)", revenue: "$112K" },
  { rank: 4, name: "王建華", avatarBg: "#FCE7F3", orders: 75, completionRate: 91, rating: "4.6 ★", turnaround: "2.5hr", rejectionRate: "3.2%", rejectionColor: "var(--text-secondary)", revenue: "$105K" },
  { rank: 5, name: "李佳穎", avatarBg: "#D1FAE5", orders: 71, completionRate: 89, rating: "4.5 ★", turnaround: "2.7hr", rejectionRate: "3.5%", rejectionColor: "var(--text-secondary)", revenue: "$98K" },
  { rank: 6, name: "黃明德", avatarBg: "#FEE2E2", orders: 68, completionRate: 87, rating: "4.4 ★", turnaround: "2.9hr", rejectionRate: "4.1%", rejectionColor: "var(--status-warning)", revenue: "$92K" },
  { rank: 7, name: "吳雅琪", avatarBg: "#EDE9FE", orders: 64, completionRate: 84, rating: "4.3 ★", turnaround: "3.2hr", rejectionRate: "4.8%", rejectionColor: "var(--status-warning)", revenue: "$85K" },
  { rank: 8, name: "蔡宗翰", avatarBg: "#CFFAFE", orders: 60, completionRate: 80, rating: "4.1 ★", turnaround: "3.5hr", rejectionRate: "5.2%", rejectionColor: "var(--status-danger)", revenue: "$78K" },
];

const columns = [
  { label: "排名", width: "w-[50px]" },
  { label: "技師", width: "w-[140px]" },
  { label: "完工工單", width: "w-[80px]" },
  { label: "完工率", width: "w-[160px]" },
  { label: "平均星等", width: "w-[100px]" },
  { label: "週轉時間", width: "w-[80px]" },
  { label: "拒單率", width: "w-[70px]" },
  { label: "營收貢獻", width: "w-[90px]" },
];

function PodiumBadge({ rank, borderColor }: { rank: number; borderColor: string }) {
  const bgMap: Record<number, string> = { 2: "#F1F5F9", 3: "#FFF7ED" };
  return (
    <div
      className="rounded-xl px-3 py-1"
      style={{ backgroundColor: bgMap[rank] }}
    >
      <span className="text-xs font-semibold" style={{ color: borderColor }}>
        #{rank}
      </span>
    </div>
  );
}

export default function TechnicianRankingPage() {
  const [activeSegment, setActiveSegment] = useState("本月");

  return (
    <div className="flex h-full bg-[var(--bg-page)]">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 flex-col gap-6 overflow-auto px-8 py-6">
          {/* Header */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              首頁 &gt; 報表 &gt; 技師排行
            </span>
            <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
              技師排行榜
            </h1>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
            <div className="flex rounded-lg bg-[#F1F5F9]">
              {segments.map((seg) => (
                <button
                  key={seg.label}
                  onClick={() => setActiveSegment(seg.label)}
                  className={`rounded-lg px-[14px] py-2 text-[13px] ${
                    activeSegment === seg.label
                      ? "bg-[var(--primary)] font-semibold text-white"
                      : "font-medium text-[var(--text-secondary)]"
                  }`}
                >
                  {seg.label}
                </button>
              ))}
            </div>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2">
              <span className="text-[13px] text-[var(--text-primary)]">
                排序：綜合評分
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>

            <button className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2">
              <span className="text-[13px] text-[var(--text-primary)]">
                全部區域
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
            </button>

            <div className="flex-1" />

            <button className="flex items-center gap-[6px] rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] px-4 py-2">
              <Download className="h-4 w-4 text-[var(--text-secondary)]" />
              <span className="text-[13px] text-[var(--text-primary)]">
                匯出 CSV
              </span>
            </button>
          </div>

          {/* Podium Section */}
          <div className="flex gap-4">
            {podium.map((card) => (
              <div
                key={card.rank}
                className="flex flex-1 flex-col items-center gap-3 rounded-xl bg-[var(--bg-surface)] p-6"
                style={{ border: `2px solid ${card.borderColor}` }}
              >
                {card.hasCrown && (
                  <Crown className="h-7 w-7 text-[#FBBF24]" />
                )}
                {!card.hasCrown && <PodiumBadge rank={card.rank} borderColor={card.borderColor} />}

                <div
                  className="h-20 w-20 rounded-full"
                  style={{ backgroundColor: card.avatarBg }}
                />

                <span className="text-base font-semibold text-[var(--text-primary)]">
                  {card.name}
                </span>

                <span
                  className="text-[32px] font-bold"
                  style={{ color: card.scoreColor }}
                >
                  {card.score}
                </span>
                <span className="text-xs text-[var(--text-secondary)]">
                  綜合評分
                </span>

                <div className="flex w-full items-center justify-around">
                  <div className="flex flex-col items-center gap-[2px]">
                    <span className="text-sm font-semibold text-[var(--status-success)]">
                      {card.completionRate}
                    </span>
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      完工率
                    </span>
                  </div>
                  <div className="flex flex-col items-center gap-[2px]">
                    <span className="text-sm font-semibold text-[#F59E0B]">
                      {card.rating}
                    </span>
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      評分
                    </span>
                  </div>
                  <div className="flex flex-col items-center gap-[2px]">
                    <span className="text-sm font-semibold text-[#3B82F6]">
                      {card.turnaround}
                    </span>
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      週轉
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Ranking Table */}
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
            <div className="flex items-center rounded-t-xl bg-[#F8FAFC] px-4 py-3">
              {columns.map((col) => (
                <div key={col.label} className={`${col.width}`}>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">
                    {col.label}
                  </span>
                </div>
              ))}
            </div>

            {rows.map((row) => (
              <div
                key={row.rank}
                className="flex items-center border-b border-[var(--border)] px-4 py-[10px] last:border-b-0"
              >
                <div className="w-[50px]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    {row.rank}
                  </span>
                </div>

                <div className="flex w-[140px] items-center gap-2">
                  <div
                    className="h-7 w-7 shrink-0 rounded-full"
                    style={{ backgroundColor: row.avatarBg }}
                  />
                  <span className="text-[13px] text-[var(--text-primary)]">
                    {row.name}
                  </span>
                </div>

                <div className="w-[80px]">
                  <span className="text-[13px] text-[var(--text-primary)]">
                    {row.orders}
                  </span>
                </div>

                <div className="flex w-[160px] items-center gap-2">
                  <div className="h-2 w-[100px] rounded bg-[#F1F5F9]">
                    <div
                      className="h-2 rounded bg-[var(--status-success)]"
                      style={{ width: `${row.completionRate}%` }}
                    />
                  </div>
                  <span className="text-xs text-[var(--status-success)]">
                    {row.completionRate}%
                  </span>
                </div>

                <div className="w-[100px]">
                  <span className="text-[13px] text-[#F59E0B]">
                    {row.rating}
                  </span>
                </div>

                <div className="w-[80px]">
                  <span className="text-[13px] text-[var(--text-primary)]">
                    {row.turnaround}
                  </span>
                </div>

                <div className="w-[70px]">
                  <span
                    className="text-[13px]"
                    style={{ color: row.rejectionColor }}
                  >
                    {row.rejectionRate}
                  </span>
                </div>

                <div className="w-[90px]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    {row.revenue}
                  </span>
                </div>
              </div>
            ))}

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3">
              <span className="text-[13px] text-[var(--text-secondary)]">
                顯示 1-25，共 48 筆
              </span>
              <div className="flex gap-1">
                <button className="rounded-md border border-[var(--border)] px-[10px] py-[6px] text-xs text-[var(--text-secondary)]">
                  上一頁
                </button>
                <button className="rounded-md bg-[var(--primary)] px-[10px] py-[6px] text-xs font-semibold text-white">
                  1
                </button>
                <button className="rounded-md border border-[var(--border)] px-[10px] py-[6px] text-xs text-[var(--text-primary)]">
                  2
                </button>
                <button className="rounded-md border border-[var(--border)] px-[10px] py-[6px] text-xs text-[var(--text-primary)]">
                  下一頁
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
