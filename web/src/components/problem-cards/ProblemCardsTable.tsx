"use client";

import Link from "next/link";

interface ProblemCard {
  id: string;
  symptom: string;
  status: { label: string; color: string; bg: string };
  level: { label: string; color: string; bg: string };
  progress: number;
  brand: string;
  model: string;
  time: string;
  entropyTag?: string;
}

const statusStyles: Record<string, { color: string; bg: string }> = {
  open: { color: "#6366F1", bg: "#EEF2FF" },
  diagnosing: { color: "#2563EB", bg: "#DBEAFE" },
  resolved: { color: "#10B981", bg: "#D1FAE5" },
  escalated: { color: "#EF4444", bg: "#FEE2E2" },
};

const levelStyles: Record<string, { color: string; bg: string }> = {
  L1: { color: "#64748B", bg: "#F1F5F9" },
  L2: { color: "#64748B", bg: "#F1F5F9" },
  L3: { color: "#EF4444", bg: "#FEE2E2" },
};

function progressColor(pct: number): string {
  if (pct >= 80) return "#10B981";
  if (pct >= 50) return "#F59E0B";
  return "#EF4444";
}

const cards: ProblemCard[] = [
  {
    id: "pc_a8f3d21e",
    symptom: "Yale電子鎖YDM-4109密碼無法解鎖",
    status: { label: "open", ...statusStyles.open },
    level: { label: "L1", ...levelStyles.L1 },
    progress: 35,
    brand: "Yale",
    model: "YDM-4109",
    time: "2小時前",
  },
  {
    id: "pc_b2c7e9f1",
    symptom: "Samsung SHP-DP609指紋辨識失敗",
    status: { label: "diagnosing", ...statusStyles.diagnosing },
    level: { label: "L2", ...levelStyles.L2 },
    progress: 65,
    brand: "Samsung",
    model: "SHP-DP609",
    time: "5小時前",
  },
  {
    id: "pc_d4e8a2b3",
    symptom: "Gateman F300藍牙連線異常",
    status: { label: "resolved", ...statusStyles.resolved },
    level: { label: "L1", ...levelStyles.L1 },
    progress: 100,
    brand: "Gateman",
    model: "F300",
    time: "1天前",
  },
  {
    id: "pc_f1a9c3d5",
    symptom: "美樂ENTR智慧鎖App無回應",
    status: { label: "escalated", ...statusStyles.escalated },
    level: { label: "L3", ...levelStyles.L3 },
    progress: 80,
    brand: "美樂",
    model: "ENTR",
    time: "3天前",
    entropyTag: "需人工確認",
  },
  {
    id: "pc_e7b2d4f6",
    symptom: "Philips EasyKey 9300電池異常耗電",
    status: { label: "open", ...statusStyles.open },
    level: { label: "L1", ...levelStyles.L1 },
    progress: 20,
    brand: "Philips",
    model: "9300",
    time: "4小時前",
  },
  {
    id: "pc_c5f8a1e2",
    symptom: "Yale YDR-323指紋模組故障",
    status: { label: "diagnosing", ...statusStyles.diagnosing },
    level: { label: "L2", ...levelStyles.L2 },
    progress: 55,
    brand: "Yale",
    model: "YDR-323",
    time: "8小時前",
  },
  {
    id: "pc_a3d6b9c1",
    symptom: "Samsung SHP-DR708馬達異常聲",
    status: { label: "resolved", ...statusStyles.resolved },
    level: { label: "L2", ...levelStyles.L2 },
    progress: 95,
    brand: "Samsung",
    model: "DR708",
    time: "2天前",
  },
  {
    id: "pc_b8e1f4a7",
    symptom: "Gateman V20觸控面板無反應",
    status: { label: "open", ...statusStyles.open },
    level: { label: "L1", ...levelStyles.L1 },
    progress: 15,
    brand: "Gateman",
    model: "V20",
    time: "6小時前",
  },
];

const columns = [
  { label: "卡片ID", width: "w-[180px]" },
  { label: "症狀摘要", width: "flex-1" },
  { label: "狀態", width: "w-[90px]" },
  { label: "解決層級", width: "w-[70px]" },
  { label: "完成度", width: "w-[100px]" },
  { label: "品牌", width: "w-[70px]" },
  { label: "型號", width: "w-[80px]" },
  { label: "建立時間", width: "w-[70px]" },
];

export default function ProblemCardsTable() {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]">
      {/* Header */}
      <div className="flex h-[44px] items-center bg-[var(--bg-page)] px-4">
        {columns.map((col) => (
          <div key={col.label} className={`${col.width} px-0`}>
            <span className="text-[12px] font-semibold text-[var(--text-secondary)]">
              {col.label}
            </span>
          </div>
        ))}
      </div>

      {/* Rows */}
      {cards.map((card, idx) => (
        <Link
          key={card.id}
          href={`/problem-cards/${card.id}`}
          className={`flex h-12 items-center border-b border-[var(--border)] px-4 hover:bg-[#EFF6FF] ${
            idx % 2 === 0 ? "bg-white" : "bg-[var(--bg-page)]"
          }`}
        >
          <div className="flex w-[180px] items-center gap-1">
            <span className="font-mono text-[12px] text-[var(--text-primary)]">
              {card.id}
            </span>
            {card.entropyTag && (
              <span className="rounded bg-[#FEF3C7] px-[6px] py-[2px] text-[9px] font-medium text-[#D97706]">
                {card.entropyTag}
              </span>
            )}
          </div>
          <div className="flex-1">
            <span className="text-[13px] text-[var(--text-primary)]">
              {card.symptom}
            </span>
          </div>
          <div className="w-[90px]">
            <span
              className="rounded-full px-[10px] py-1 text-[11px] font-medium"
              style={{ color: card.status.color, backgroundColor: card.status.bg }}
            >
              {card.status.label}
            </span>
          </div>
          <div className="w-[70px]">
            <span
              className="rounded px-2 py-1 text-[11px] font-medium"
              style={{ color: card.level.color, backgroundColor: card.level.bg }}
            >
              {card.level.label}
            </span>
          </div>
          <div className="flex w-[100px] items-center gap-[6px]">
            <div className="h-[6px] w-[60px] overflow-hidden rounded-[3px] bg-[#E2E8F0]">
              <div
                className="h-full rounded-[3px]"
                style={{
                  width: `${card.progress}%`,
                  backgroundColor: progressColor(card.progress),
                }}
              />
            </div>
            <span className="text-[11px] text-[var(--text-secondary)]">
              {card.progress}%
            </span>
          </div>
          <div className="w-[70px]">
            <span className="text-[13px] text-[var(--text-primary)]">
              {card.brand}
            </span>
          </div>
          <div className="w-[80px]">
            <span className="text-[13px] text-[var(--text-primary)]">
              {card.model}
            </span>
          </div>
          <div className="w-[70px]">
            <span className="text-[12px] text-[var(--text-secondary)]">
              {card.time}
            </span>
          </div>
        </Link>
      ))}

      {/* Pagination */}
      <div className="flex h-12 items-center justify-between px-4">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 1-8，共 193 筆
        </span>
        <div className="flex gap-1">
          {["1", "2", "3", "...", "10"].map((page, i) => (
            <button
              key={i}
              className={`flex h-8 w-8 items-center justify-center rounded-md text-[13px] ${
                page === "1"
                  ? "bg-[var(--primary)] font-semibold text-white"
                  : "border border-[var(--border)] bg-white text-[var(--text-primary)]"
              }`}
            >
              {page}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
