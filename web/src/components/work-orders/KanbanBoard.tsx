"use client";

import { Timer, CircleX, AlertTriangle } from "lucide-react";
import Link from "next/link";

interface KanbanCard {
  id: string;
  status: { label: string; color: string; bg: string };
  customer: string;
  address: string;
  brand: string;
  technician: { name: string; color: string } | null;
  sla: { text: string; color?: string; bold?: boolean; icon?: "timer" | "warning" | "overdue" | "none" };
}

interface KanbanColumn {
  title: string;
  color: string;
  count: string;
  cards: KanbanCard[];
}

const columns: KanbanColumn[] = [
  {
    title: "待指派",
    color: "#6366F1",
    count: "5",
    cards: [
      {
        id: "WO-20260422-0001",
        status: { label: "待指派", color: "#6366F1", bg: "#EEF2FF" },
        customer: "陳小姐",
        address: "台北市大安區...",
        brand: "Yale YDM-4109",
        technician: null,
        sla: { text: "剩餘 02:45", icon: "timer" },
      },
      {
        id: "WO-20260422-0004",
        status: { label: "待指派", color: "#6366F1", bg: "#EEF2FF" },
        customer: "謬志強",
        address: "新北市永和區...",
        brand: "Samsung P718",
        technician: null,
        sla: { text: "剩餘 05:10", icon: "timer" },
      },
      {
        id: "WO-20260422-0006",
        status: { label: "待指派", color: "#6366F1", bg: "#EEF2FF" },
        customer: "張雅雯",
        address: "台中市北區...",
        brand: "Philips 9300",
        technician: null,
        sla: { text: "剩餘 03:30", icon: "timer" },
      },
    ],
  },
  {
    title: "已派工",
    color: "#8B5CF6",
    count: "3",
    cards: [
      {
        id: "WO-20260422-0002",
        status: { label: "已派工", color: "#8B5CF6", bg: "#F5F3FF" },
        customer: "王大明",
        address: "新北市板橋區...",
        brand: "Samsung DP609",
        technician: { name: "李技師", color: "#C4B5FD" },
        sla: { text: "剩餘 01:30", icon: "timer" },
      },
      {
        id: "WO-20260422-0005",
        status: { label: "已派工", color: "#8B5CF6", bg: "#F5F3FF" },
        customer: "林志明",
        address: "桃園市中壢...",
        brand: "Yale YDR-323",
        technician: { name: "張師傅", color: "#C4B5FD" },
        sla: { text: "剩餘 04:00", icon: "timer" },
      },
    ],
  },
  {
    title: "進行中",
    color: "#3B82F6",
    count: "4",
    cards: [
      {
        id: "WO-20260422-0003",
        status: { label: "進行中", color: "#3B82F6", bg: "#DBEAFE" },
        customer: "林美華",
        address: "台中市西屯...",
        brand: "Gateman F300",
        technician: { name: "張師傅", color: "#93C5FD" },
        sla: { text: "剩餘 04:20", icon: "timer" },
      },
      {
        id: "WO-20260421-0018",
        status: { label: "進行中", color: "#3B82F6", bg: "#DBEAFE" },
        customer: "黃志明",
        address: "高雄市左營...",
        brand: "美樂 ENTR",
        technician: { name: "謬師傅", color: "#93C5FD" },
        sla: { text: "剩餘 00:25", color: "#F59E0B", bold: true, icon: "warning" },
      },
      {
        id: "WO-20260421-0012",
        status: { label: "進行中", color: "#3B82F6", bg: "#DBEAFE" },
        customer: "劉家豪",
        address: "台北市信義...",
        brand: "Philips 9300",
        technician: { name: "吴技師", color: "#93C5FD" },
        sla: { text: "逾時 01:15", color: "#EF4444", bold: true, icon: "overdue" },
      },
    ],
  },
  {
    title: "已完工",
    color: "#10B981",
    count: "6",
    cards: [
      {
        id: "WO-20260420-0008",
        status: { label: "已完工", color: "#10B981", bg: "#D1FAE5" },
        customer: "趙雅婷",
        address: "桃園市中壢...",
        brand: "Yale YDR-323",
        technician: { name: "陳師傅", color: "#6EE7B7" },
        sla: { text: "--", color: "var(--text-disabled)", icon: "none" },
      },
      {
        id: "WO-20260420-0003",
        status: { label: "已完工", color: "#10B981", bg: "#D1FAE5" },
        customer: "周建國",
        address: "新竹市東區...",
        brand: "Samsung DR708",
        technician: { name: "李技師", color: "#6EE7B7" },
        sla: { text: "--", color: "var(--text-disabled)", icon: "none" },
      },
    ],
  },
  {
    title: "異常",
    color: "#EF4444",
    count: "2",
    cards: [
      {
        id: "WO-20260421-0015",
        status: { label: "delayed", color: "#D97706", bg: "#FEF3C7" },
        customer: "黃志明",
        address: "高雄市左營...",
        brand: "美樂 ENTR",
        technician: { name: "謬師傅", color: "#FCA5A5" },
        sla: { text: "剩餘 00:25", color: "#F59E0B", bold: true, icon: "warning" },
      },
      {
        id: "WO-20260420-0005",
        status: { label: "rework", color: "#EF4444", bg: "#FEE2E2" },
        customer: "周建國",
        address: "新竹市東區...",
        brand: "Samsung DR708",
        technician: { name: "李技師", color: "#FCA5A5" },
        sla: { text: "剩餘 03:00", icon: "timer" },
      },
    ],
  },
];

function SlaIndicator({ sla }: { sla: KanbanCard["sla"] }) {
  const color = sla.color || "var(--text-secondary)";

  if (sla.icon === "none") {
    return (
      <span className="text-[11px] font-medium" style={{ color }}>
        {sla.text}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1">
      {sla.icon === "overdue" ? (
        <CircleX className="h-[14px] w-[14px]" style={{ color }} />
      ) : sla.icon === "warning" ? (
        <AlertTriangle className="h-[14px] w-[14px]" style={{ color }} />
      ) : (
        <Timer className="h-[14px] w-[14px]" style={{ color }} />
      )}
      <span
        className={`text-[11px] font-medium ${sla.bold ? "font-bold" : ""}`}
        style={{ color }}
      >
        {sla.text}
      </span>
    </div>
  );
}

function CardItem({ card, columnColor }: { card: KanbanCard; columnColor: string }) {
  return (
    <Link
      href={`/work-orders/${card.id}`}
      className="flex flex-col gap-[10px] rounded-lg bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
      style={{ borderLeft: `3px solid ${columnColor}` }}
    >
      {/* Top row */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] font-medium text-[var(--text-secondary)]">
          {card.id}
        </span>
        <span
          className="rounded px-2 py-[2px] text-[11px] font-semibold"
          style={{ color: card.status.color, backgroundColor: card.status.bg }}
        >
          {card.status.label}
        </span>
      </div>

      {/* Mid section */}
      <div className="flex flex-col gap-1">
        <span className="text-[14px] font-semibold text-[var(--text-primary)]">
          {card.customer}
        </span>
        <span className="text-[12px] text-[var(--text-secondary)]">
          {card.address}
        </span>
        <span className="text-[12px] text-[var(--text-secondary)]">
          {card.brand}
        </span>
      </div>

      {/* Divider */}
      <div className="h-px w-full bg-[var(--border)]" />

      {/* Bottom row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[6px]">
          {card.technician ? (
            <>
              <div
                className="h-5 w-5 flex-shrink-0 rounded-full"
                style={{ backgroundColor: card.technician.color }}
              />
              <span className="text-[12px] font-medium text-[var(--text-primary)]">
                {card.technician.name}
              </span>
            </>
          ) : (
            <>
              <div className="h-5 w-5 flex-shrink-0 rounded-full bg-[#E2E8F0]" />
              <span className="text-[12px] italic text-[var(--text-disabled)]">
                未指派
              </span>
            </>
          )}
        </div>
        <SlaIndicator sla={card.sla} />
      </div>
    </Link>
  );
}

export default function KanbanBoard() {
  return (
    <div className="flex h-full gap-4 p-4">
      {columns.map((col) => (
        <div
          key={col.title}
          className="flex flex-1 flex-col rounded-lg bg-[#F8FAFC]"
          style={{ borderTop: `3px solid ${col.color}` }}
        >
          {/* Column Header */}
          <div className="flex h-12 items-center justify-between px-3">
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              {col.title}
            </span>
            <span
              className="rounded-[10px] px-2 py-[2px] text-[12px] font-semibold text-white"
              style={{ backgroundColor: col.color }}
            >
              {col.count}
            </span>
          </div>

          {/* Column Body */}
          <div className="flex flex-1 flex-col gap-3 overflow-auto px-3 pb-3">
            {col.cards.map((card) => (
              <CardItem key={card.id} card={card} columnColor={col.color} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
