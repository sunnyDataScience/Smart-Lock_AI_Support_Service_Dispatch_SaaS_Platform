"use client";

import CaseCard from "./CaseCard";

interface CaseItem {
  id: string;
  title: string;
  brand: string;
  model?: string;
  accuracy: number;
  usageCount: number;
  updatedAt: string;
}

const cases: CaseItem[] = [
  {
    id: "case-001",
    title: "Yale YDM-4109 密碼無法解鎖解決方案",
    brand: "Yale",
    model: "YDM-4109",
    accuracy: 92,
    usageCount: 47,
    updatedAt: "2小時前",
  },
  {
    id: "case-002",
    title: "Samsung SHP-DP609 指紋辨識故障排除",
    brand: "Samsung",
    model: "SHP-DP609",
    accuracy: 85,
    usageCount: 34,
    updatedAt: "1天前",
  },
  {
    id: "case-003",
    title: "Gateman F300 藍牙連線異常處理",
    brand: "Gateman",
    model: "F300",
    accuracy: 78,
    usageCount: 21,
    updatedAt: "2天前",
  },
  {
    id: "case-004",
    title: "美樂 ENTR App無回應處理流程",
    brand: "美樂",
    model: "ENTR",
    accuracy: 65,
    usageCount: 15,
    updatedAt: "3天前",
  },
  {
    id: "case-005",
    title: "Philips 9300 電池異常耗電診斷",
    brand: "Philips",
    model: "9300",
    accuracy: 88,
    usageCount: 28,
    updatedAt: "4天前",
  },
  {
    id: "case-006",
    title: "Yale YDR-323 指紋模組更換指南",
    brand: "Yale",
    model: "YDR-323",
    accuracy: 95,
    usageCount: 52,
    updatedAt: "1週前",
  },
  {
    id: "case-007",
    title: "Samsung DR708 馬達異音排除",
    brand: "Samsung",
    model: "DR708",
    accuracy: 42,
    usageCount: 8,
    updatedAt: "2週前",
  },
  {
    id: "case-008",
    title: "Gateman V20 觸控面板重置",
    brand: "Gateman",
    model: "V20",
    accuracy: 71,
    usageCount: 19,
    updatedAt: "5天前",
  },
  {
    id: "case-009",
    title: "通用電子鎖電池更換 SOP",
    brand: "通用",
    accuracy: 97,
    usageCount: 89,
    updatedAt: "3天前",
  },
  {
    id: "case-010",
    title: "Yale YDM-7220 韌體更新指南",
    brand: "Yale",
    model: "YDM-7220",
    accuracy: 80,
    usageCount: 12,
    updatedAt: "1週前",
  },
  {
    id: "case-011",
    title: "Samsung P718 防盜警報誤觸發",
    brand: "Samsung",
    model: "P718",
    accuracy: 55,
    usageCount: 6,
    updatedAt: "2週前",
  },
  {
    id: "case-012",
    title: "Gateman G-Swipe 卡片讀取失敗",
    brand: "Gateman",
    model: "G-Swipe",
    accuracy: 38,
    usageCount: 3,
    updatedAt: "3週前",
  },
];

const totalItems = 128;
const totalPages = 11;
const currentPage = 1;
const itemsPerPage = 12;

export default function CaseCardGrid() {
  const pages = [1, 2, 3, null, totalPages];

  return (
    <div className="flex flex-1 flex-col gap-5 px-8 py-6">
      <div className="grid grid-cols-3 gap-5">
        {cases.map((c) => (
          <CaseCard
            key={c.id}
            id={c.id}
            title={c.title}
            brand={c.brand}
            model={c.model}
            accuracy={c.accuracy}
            usageCount={c.usageCount}
            updatedAt={c.updatedAt}
          />
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[13px] text-[var(--text-secondary)]">
          顯示 1-{itemsPerPage}，共 {totalItems} 筆
        </span>

        <div className="flex items-center gap-1">
          {pages.map((page, idx) =>
            page === null ? (
              <span
                key={`dots-${idx}`}
                className="flex h-8 w-8 items-center justify-center text-[13px] text-[var(--text-secondary)]"
              >
                ...
              </span>
            ) : (
              <button
                key={page}
                className={`flex h-8 w-8 items-center justify-center rounded-md text-[13px] ${
                  page === currentPage
                    ? "bg-[var(--primary)] font-semibold text-white"
                    : "border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)]"
                }`}
              >
                {page}
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
