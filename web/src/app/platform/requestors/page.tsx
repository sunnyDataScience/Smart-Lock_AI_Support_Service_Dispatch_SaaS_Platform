"use client";

// CR-0114 收尾 — 平台 console「發案方審核」。
// 品牌申請（導入意向）與廠商帳號（發案登入帳號）都是「發案的一方」（相對於師傅=
// 接案方），業主指示合成同一頁。兩者資料模型與審核動作不同（品牌申請核准要填代號
// + 出開站指引；廠商核准是啟用帳號）→ 用分頁分隔,不硬混成一張清單。
// 內部工具 → 文案直接繁中。

import { useState } from "react";
import BrandApplicationsPanel from "@/components/platform/BrandApplicationsPanel";
import VendorsPanel from "@/components/platform/VendorsPanel";

type Tab = "applications" | "vendors";

const TABS: { value: Tab; label: string }[] = [
  { value: "applications", label: "品牌申請" },
  { value: "vendors", label: "廠商帳號" },
];

export default function RequestorsReviewPage() {
  const [tab, setTab] = useState<Tab>("applications");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">發案方審核</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          品牌／經銷／鎖店（發案的一方）的平台導入申請與發案帳號審核。由平台方統一負責。
        </p>
      </div>

      {/* 分頁切換 */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map((t) => {
          const active = tab === t.value;
          return (
            <button
              key={t.value}
              type="button"
              onClick={() => setTab(t.value)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
                active
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "applications" ? <BrandApplicationsPanel /> : <VendorsPanel />}
    </div>
  );
}
