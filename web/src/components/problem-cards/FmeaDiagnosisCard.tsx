"use client";

import {
  CircleAlert,
  Zap,
  TriangleAlert,
  CircleX,
  ArrowRight,
} from "lucide-react";

interface FmeaNode {
  icon: React.ElementType;
  label: string;
  text: string;
  color: string;
  bg: string;
  borderColor: string;
}

const nodes: FmeaNode[] = [
  {
    icon: CircleAlert,
    label: "Symptom",
    text: "輸入密碼後無法解鎖，螢幕顯示E3",
    color: "#2563EB",
    bg: "#DBEAFE",
    borderColor: "#2563EB",
  },
  {
    icon: Zap,
    label: "Failure",
    text: "離合器模組機械傳動失效",
    color: "#6366F1",
    bg: "#E0E7FF",
    borderColor: "#6366F1",
  },
  {
    icon: TriangleAlert,
    label: "Failure Mode",
    text: "離合器齒輪磨損導致傳動力不足",
    color: "#D97706",
    bg: "#FEF3C7",
    borderColor: "#F59E0B",
  },
  {
    icon: CircleX,
    label: "Defect",
    text: "離合器組件製造缺陷，需更換",
    color: "#EF4444",
    bg: "#FEE2E2",
    borderColor: "#EF4444",
  },
];

const arrows = ["推斷", "分析", "根因"];

export default function FmeaDiagnosisCard() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <div className="flex flex-col gap-5">
        <div>
          <h2 className="text-[18px] font-bold text-[var(--text-primary)]">
            FMEA 診斷推理鏈
          </h2>
          <p className="text-[13px] text-[var(--text-secondary)]">
            Symptom → Failure → Failure Mode → Defect 四層推理過程
          </p>
        </div>

        <div className="flex w-full items-center justify-center">
          {nodes.map((node, i) => (
            <div key={node.label} className="flex items-center">
              <div
                className="flex w-[140px] flex-col items-center gap-[6px] rounded-xl p-3 px-4"
                style={{
                  backgroundColor: node.bg,
                  border: `2px solid ${node.borderColor}`,
                }}
              >
                <node.icon
                  className="h-6 w-6"
                  style={{ color: node.color }}
                />
                <span
                  className="text-center text-[10px] font-semibold"
                  style={{ color: node.color }}
                >
                  {node.label}
                </span>
                <span className="text-center text-[11px] text-[var(--text-primary)]">
                  {node.text}
                </span>
              </div>

              {i < nodes.length - 1 && (
                <div className="flex w-10 flex-col items-center gap-[2px]">
                  <ArrowRight className="h-5 w-5 text-[var(--text-secondary)]" />
                  <span className="text-center text-[9px] text-[var(--text-secondary)]">
                    {arrows[i]}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
