"use client";

import { X } from "lucide-react";

interface TechnicianCandidate {
  rank: number;
  name: string;
  avatarColor: string;
  rating?: string;
  aiBadge?: boolean;
  status: { label: string; textColor: string; bgColor: string };
  scores: { distance: string; skill: string; rating: string; load: string };
  total: { score: string; bgColor: string };
  rankColor: string;
  highlighted?: boolean;
}

const candidates: TechnicianCandidate[] = [
  {
    rank: 1,
    name: "李建宏",
    avatarColor: "#CBD5E1",
    aiBadge: true,
    status: { label: "空閒", textColor: "#10B981", bgColor: "transparent" },
    scores: {
      distance: "距離 92% (3.2km)",
      skill: "技能 95%",
      rating: "評分 96%",
      load: "負荷 88% (2單)",
    },
    total: { score: "93分", bgColor: "#10B981" },
    rankColor: "var(--primary)",
    highlighted: true,
  },
  {
    rank: 2,
    name: "張志明",
    avatarColor: "#94A3B8",
    rating: "4.5 ★",
    status: { label: "作業中 (3單)", textColor: "#92400E", bgColor: "#FEF3C7" },
    scores: {
      distance: "距離 85% (5.1km)",
      skill: "技能 90%",
      rating: "評分 90%",
      load: "負荷 75% (3單)",
    },
    total: { score: "85分", bgColor: "var(--primary)" },
    rankColor: "var(--text-secondary)",
  },
  {
    rank: 3,
    name: "陳小華",
    avatarColor: "#CBD5E1",
    rating: "4.3 ★",
    status: { label: "空閒", textColor: "#065F46", bgColor: "#D1FAE5" },
    scores: {
      distance: "距離 78% (8.2km)",
      skill: "技能 88%",
      rating: "評分 86%",
      load: "負荷 92% (1單)",
    },
    total: { score: "86分", bgColor: "var(--primary)" },
    rankColor: "var(--text-secondary)",
  },
  {
    rank: 4,
    name: "王大同",
    avatarColor: "#E2E8F0",
    rating: "4.0 ★",
    status: { label: "空閒", textColor: "#065F46", bgColor: "#D1FAE5" },
    scores: {
      distance: "距離 65% (12km)",
      skill: "技能 82%",
      rating: "評分 80%",
      load: "負荷 95% (0單)",
    },
    total: { score: "80分", bgColor: "var(--primary)" },
    rankColor: "var(--text-secondary)",
  },
  {
    rank: 5,
    name: "劉民雄",
    avatarColor: "#E2E8F0",
    rating: "3.8 ★",
    status: { label: "作業中 (4單)", textColor: "#92400E", bgColor: "#FEF3C7" },
    scores: {
      distance: "距離 45% (18km)",
      skill: "技能 75%",
      rating: "評分 76%",
      load: "負荷 70% (4單)",
    },
    total: { score: "66分", bgColor: "var(--accent)" },
    rankColor: "var(--text-disabled)",
  },
];

function CandidateRow({ c }: { c: TechnicianCandidate }) {
  return (
    <div
      className={`flex items-center gap-3 px-6 py-[14px] ${
        c.highlighted ? "bg-[#F0F9FF]" : "bg-white"
      }`}
      style={{
        borderBottom:
          c.rank < 5 ? "1px solid var(--border)" : undefined,
      }}
    >
      {/* Rank */}
      <span
        className="text-[20px] font-extrabold"
        style={{ color: c.rankColor }}
      >
        #{c.rank}
      </span>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-[6px]">
        <div className="flex items-center gap-2">
          <div
            className="h-9 w-9 flex-shrink-0 rounded-full"
            style={{ backgroundColor: c.avatarColor }}
          />
          <div className="flex flex-col gap-[2px]">
            <span className="text-[14px] font-semibold text-[var(--text-primary)]">
              {c.name}
            </span>
            <div className="flex items-center gap-[6px]">
              {c.aiBadge && (
                <span className="rounded-[9px] border border-[#6366F1] bg-[#EEF2FF] px-2 text-[10px] font-semibold leading-[18px] text-[#6366F1]">
                  AI 推薦
                </span>
              )}
              {c.rating && (
                <span className="text-[11px] font-semibold text-[var(--accent)]">
                  {c.rating}
                </span>
              )}
              {c.status.bgColor !== "transparent" ? (
                <span
                  className="rounded px-[6px] py-[2px] text-[10px] font-medium"
                  style={{
                    color: c.status.textColor,
                    backgroundColor: c.status.bgColor,
                  }}
                >
                  {c.status.label}
                </span>
              ) : (
                <span
                  className="text-[11px] font-medium"
                  style={{ color: c.status.textColor }}
                >
                  {c.status.label}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-[11px] text-[var(--text-secondary)]">
            {c.scores.distance}
          </span>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {c.scores.skill}
          </span>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {c.scores.rating}
          </span>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {c.scores.load}
          </span>
        </div>
      </div>

      {/* Right: score + assign */}
      <div className="flex flex-col items-center gap-2">
        <span
          className="rounded-full px-3 text-[13px] font-bold leading-7 text-white"
          style={{ backgroundColor: c.total.bgColor }}
        >
          {c.total.score}
        </span>
        <button className="flex h-[30px] items-center justify-center rounded-md bg-[var(--primary)] px-[14px]">
          <span className="text-[12px] font-semibold text-white">指派</span>
        </button>
      </div>
    </div>
  );
}

interface AssignTechnicianModalProps {
  isOpen: boolean;
  onClose: () => void;
  workOrderId?: string;
}

export default function AssignTechnicianModal({
  isOpen,
  onClose,
  workOrderId = "WO-20260422-0001",
}: AssignTechnicianModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/24"
      onClick={onClose}
    >
      <div
        className="flex w-[640px] flex-col rounded-xl bg-[var(--bg-surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-5">
          <span className="text-[18px] font-bold text-[var(--text-primary)]">
            指派技師 — {workOrderId}
          </span>
          <X
            className="h-5 w-5 cursor-pointer text-[var(--text-secondary)]"
            onClick={onClose}
          />
        </div>

        {/* WO Summary */}
        <div className="flex flex-col gap-2 bg-[#F8FAFC] px-6 py-4">
          <div className="flex gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              客戶：
            </span>
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              陳小姐
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              地址：
            </span>
            <span className="text-[13px] text-[var(--text-primary)]">
              台北市大安區忠孝東路四段100號12F
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              品牌型號：
            </span>
            <span className="text-[13px] text-[var(--text-primary)]">
              Yale YDM-4109
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-[13px] text-[var(--text-secondary)]">
              問題摘要：
            </span>
            <span className="text-[13px] text-[var(--text-primary)]">
              密碼無法解鎖，螢幕顯示E3錯誤代碼
            </span>
          </div>
        </div>

        {/* Candidate Header */}
        <div className="flex flex-col gap-1 px-6 pb-2 pt-4">
          <span className="text-[16px] font-bold text-[var(--text-primary)]">
            推薦技師
          </span>
          <span className="text-[12px] text-[var(--text-secondary)]">
            根據距離、技能、評分、負荷綜合評估
          </span>
        </div>

        {/* Candidate List */}
        <div className="flex flex-col">
          {candidates.map((c) => (
            <CandidateRow key={c.rank} c={c} />
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end border-t border-[var(--border)] px-6 py-4">
          <button
            className="rounded-lg border border-[var(--border)] px-6 py-2"
            onClick={onClose}
          >
            <span className="text-[14px] font-medium text-[var(--text-secondary)]">
              取消
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
